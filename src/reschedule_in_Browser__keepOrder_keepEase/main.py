# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Copyright 2018 ijgnd

# this add-on mainly modifies functions from anki 
# which is 
#          Copyright: Damien Elmes <anki@ichi2.net>
# (for details see comments)



#####BEGIN USER CONFIG####
RedefineReschedCards = True
CheckKeepEaseByDefault = True
#####END USER CONFIG######


import random

from aqt.browser import Browser
from anki.sched import Scheduler
from aqt.qt import *
from anki.utils import intTime
from anki.hooks import addHook

from .forms import reschedule_dialog
from .forms import reschedule_in_order


# mainly a mod of sched.py - reschedCards
def reschedHelper(self, cid_list, factor, imin, imax):
    "Put cards in review queue with a new interval in days (min, max)."
    d = []
    t = self.today
    mod = intTime()
    for id in cid_list:
        r = random.randint(imin, imax)
        d.append(dict(id=id, due=r+t, ivl=max(1, r), mod=mod,
                        usn=self.col.usn(), fact=int(factor)))
    self.col.db.executemany("""
update cards set type=2,queue=2,ivl=:ivl,due=:due,odue=0,
usn=:usn,mod=:mod,factor=:fact where id=:id""",
                            d)
    self.col.log(cid_list)
Scheduler.reschedHelper = reschedHelper


from collections import defaultdict
def ReschedCardsKeepEase(self, cid_list, imin, imax):
    EaseForCards = defaultdict(list)
    self.remFromDyn(cid_list)   # as in rescheduleCards
    for i in cid_list:
        card = self.col.getCard(i)
        if card.type == 2:  #cards in state "review"
            factor = card.factor
        else: # card.type 0,1 new,learning
            conf = self.col.decks.confForDid(card.did)
            factor = conf['new']['initialFactor']
        EaseForCards[factor].append(i)
    for fct,card_ids in EaseForCards.items():
        self.reschedHelper(card_ids, fct, imin, imax)
Scheduler.ReschedCardsKeepEase = ReschedCardsKeepEase



#overwrite this function from browser.py
def reschedule(self):
    d = QDialog(self)
    d.setWindowModality(Qt.WindowModal)
    frm = reschedule_dialog.Ui_Dialog()
    frm.setupUi(d)
    num_selected_cards = len(self.selectedCards())
    frm.label_beg.setText("spread selected %d cards over" % num_selected_cards)
    frm.label_middle.setText("days and delay by")
    frm.label_end.setText("days")
    if CheckKeepEaseByDefault:
        frm.keepEase.setCheckState(1)
    if not d.exec_():
        return
    self.model.beginReset()
    self.mw.checkpoint(_("Reschedule"))
    #self.frm.label_before.setText("hola")
    if frm.asNew.isChecked():
        self.col.sched.forgetCards(self.selectedCards())
    elif frm.asRev.isChecked():
        fmin = frm.min.value()
        fmax = frm.max.value()
        fmax = max(fmin, fmax)
        if frm.keepEase.checkState():
            self.col.sched.ReschedCardsKeepEase(self.selectedCards(), fmin, fmax)
        else:
            self.col.sched.reschedCardsResetEase(self.selectedCards(), fmin, fmax)
    else:
        days = frm.spinBox_spread.value()
        delay = frm.spinBox_delay.value()
        self.col.sched.reschedCardsInOrder(self.selectedCards(), days, delay,frm.keepEase.checkState())
    self.onSearch(reset=False)
    self.mw.requireReset()
    self.model.endReset()
Browser.reschedule=reschedule




def reschedule_only_in_order(self):
    d = QDialog(self)
    d.setWindowModality(Qt.WindowModal)
    frm = reschedule_in_order.Ui_PlaceInReviewQueueInOrder_Dialog()
    frm.setupUi(d)
    frm.spinBox_spread.cleanText()
    num_selected_cards = len(self.selectedCards())
    frm.label_beg.setText("spread selected %d cards over" % num_selected_cards)
    frm.label_middle.setText("days and delay by")
    frm.label_end.setText("days")
    if CheckKeepEaseByDefault:
        frm.keepEase.setCheckState(1)
    if not d.exec_():
        return
    self.model.beginReset()
    self.mw.checkpoint(_("Reschedule"))
    days = frm.spinBox_spread.value()
    delay = frm.spinBox_delay.value()
    keepEase = frm.keepEase.checkState()
    self.col.sched.reschedCardsInOrder(self.selectedCards(), days, delay, keepEase)
    self.onSearch(reset=False)
    self.mw.requireReset()
    self.model.endReset()




#extensive mod of sched.py - reschedCards
def reschedCardsInOrder(self, cid_list, days, delay, keepEase=False):
    """
    Put cards in review queue over days starting from today+delay
    This function is slow and intended only for a few cards.
    """
    self.remFromDyn(cid_list)  #this is in reschedCards but not in my reschedHelper. So I must put it here.

    cards=len(cid_list)
    if days == 0:
        cards_per_day=cards
    else:
        cards_per_day=cards/(days+1)
    lower = int(cards_per_day)
    cards_distributed = 0

    #preliminary without delay:
    list_of_due_cards_per_day = [] #first entry with index zero is today and so on.

    for i in range(days+1):
        list_of_due_cards_per_day.append(lower)
        cards_distributed += lower

    while cards > cards_distributed:
        target = list_of_due_cards_per_day.index(min(list_of_due_cards_per_day))
        list_of_due_cards_per_day[target] += 1
        cards_distributed += 1

    random.shuffle(list_of_due_cards_per_day)

    #prepend delay
    prepend_list = [0] * delay
    list_of_due_cards_per_day = prepend_list + list_of_due_cards_per_day

    list_when_will_be_cards_due = []  # first entry is interval of first card and so on.
    for k,v in enumerate(list_of_due_cards_per_day):
        for i in range(v):
            list_when_will_be_cards_due.append(k)

    for i, cid in enumerate(cid_list):
        if keepEase:
            card = self.col.getCard(cid)
            if card.type == 2:   #card type is "review"
                myfactor = card.factor
            else: # card.type 0,1 new,learning - these don't have a card factor
                conf = self.col.decks.confForDid(card.did)
                myfactor = conf['new']['initialFactor']
        else:
            myfactor = 2500

        r = list_when_will_be_cards_due[i]  
        self.reschedHelper([cid],myfactor,r,r)
Scheduler.reschedCardsInOrder=reschedCardsInOrder




def onSetupMenus(self):
    menu = self.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('Reschedule Selected Cards in ORDER')
    a.setShortcut(QKeySequence("Alt+R"))
    a.triggered.connect(lambda _, o=self: reschedule_only_in_order(o))

addHook("browser.setupMenus", onSetupMenus)


if RedefineReschedCards:
    Scheduler.reschedCardsResetEase = Scheduler.reschedCards
    Scheduler.reschedCards = Scheduler.ReschedCardsKeepEase

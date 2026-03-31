from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


# Global accounts dictionary (shared by all actions)
accounts = {
    "12345": 50000,
    "67890": 120000,
    "11111": 7500,
    "22222": 25000
}


class ActionCheckBalance(Action):

    def name(self) -> Text:
        return "action_check_balance"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        account_number = tracker.get_slot("account_number")

        if account_number in accounts:
            balance = accounts[account_number]
            dispatcher.utter_message(text=f"Your current balance is ₹{balance}")
        else:
            dispatcher.utter_message(text="Account number not found.")

        return [SlotSet("account_number", None)]


class ActionTransferMoney(Action):

    def name(self) -> Text:
        return "action_transfer_money"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        sender = tracker.get_slot("sender_account")
        receiver = tracker.get_slot("receiver_account")
        amount = tracker.get_slot("transfer_amount")

        amount = int(amount)

        if sender not in accounts:
            dispatcher.utter_message(text="Sender account not found.")
            return []

        if receiver not in accounts:
            dispatcher.utter_message(text="Receiver account not found.")
            return []

        if accounts[sender] < amount:
            dispatcher.utter_message(text="Insufficient balance.")
            return []

        # Transfer logic
        accounts[sender] -= amount
        accounts[receiver] += amount

        dispatcher.utter_message(
            text=f"₹{amount} has been successfully transferred from account {sender} to account {receiver}."
        )

        dispatcher.utter_message(
            text=f"Your current balance is ₹{accounts[sender]}"
        )

        return [
            SlotSet("sender_account", None),
            SlotSet("receiver_account", None),
            SlotSet("transfer_amount", None)
        ]
from celery import shared_task
import logging 
from common.models import Order
from .models import Transaction
from datetime import datetime
from django.utils import timezone
from django.utils.timezone import make_aware
import zeep 
from django.conf import settings
from django.contrib.auth.models import User
from itertools import chain
from operator import attrgetter

@shared_task
def expireOrders():
    logging.error("Running order expiry")
    orders = Order.objects.all().filter(expiry_date__lte=timezone.now(), status='A')
    for order in orders:
        order.status = Order.EXPIRED
        logging.error("Expirying order {}".format(order.expiry_date))
        order.save()


@shared_task
def getUserTransactions(user_id):
    logging.info("get user transactions")
    transpact_terminal_states = ['Transaction Completed', 'Voided']
    wsdl = settings.TRANSPACT_WSDL
    transapact_user_admin = settings.TRANSPACT_PARTNER_USERNAME
    password= settings.TRANSPACT_PARTNER_PASSWORD
    client = zeep.Client(wsdl=wsdl, service_name='Partner', port_name='PartnerSoap')
    logging.info("going to transpact")
    user = User.objects.get(pk=user_id)

    # changing to use ViewPayerTranspacts and ViewPayeeTranspacts
    with client.settings(raw_response=False):
        logging.warning("running get transactions for user {}".format(user.email))
        # TODO:i think i need to do ViewPayerTranspacts and ViewPayeeTranspacts too
        try:
            r = client.service.ViewPayeeTranspacts(Username=transapact_user_admin, Password=password,
                IsTest=settings.TRANSPACT_IS_TEST, ClientEmail=user.email)
            logging.debug(type(r))

            s = client.service.ViewPayerTranspacts(Username=transapact_user_admin, Password=password,
                IsTest=settings.TRANSPACT_IS_TEST, ClientEmail=user.email)
            logging.debug(type(s))

            # Handle None responses from API
            r = r if r is not None else []
            s = s if s is not None else []
            res = list(r) + list(s)
        except Exception as e:
            logging.error(f"Error fetching Transpact transactions: {str(e)}")
            return
        logging.info(f"{len(r)} transactions")
        for t in res:
            # logging.error(len(r))
            # logging.error(t['Status'])
            # logging.error(t['PartnerReference'])
            if (t['PartnerReference'] == "uejn7ubk4z"):
                logging.info("this one^V")
            else:
                logging.info("...")
            # None if none found
            transaction = Transaction.objects.filter(transaction_reference=t['PartnerReference']).first()
            # if transaction is None:
            #     logging.error('Not found')
            # else:
            #     logging.error(t['Status'])
            #     logging.error(t['PartnerReference'])
            #     logging.error(t['TranspactNumber'])

            if transaction is not None:
                logging.info(transaction.transpact_text_status)
                logging.info(t['Status'])

                if transaction.transpact_text_status != t['Status']:
                    transaction.transpact_text_status = t['Status']
                    transaction.transpact_update_datetime = make_aware(datetime.now())
                    # logging.error(t['Status'])
                    # add transaction mapping
                    # transaction status:
                    if t['Status'] == 'Created: Waiting for Both Parties to Accept or Reject Terms':
                        transaction.transaction_status = transaction.PENDING_BOTH
                    elif t['Status'] == 'Recipient Accepted: Waiting for Payer to Accept Terms':
                        transaction.transaction_status = transaction.PENDING_BUYER
                    elif t['Status'] == 'Waiting for Payer to pay, Recipient to Accept Terms':
                        transaction.transaction_status = transaction.PENDING_SELLER
                    elif t['Status'] == 'Waiting for Recipient to pay, Payer to Accept Terms':
                        # this is the initial payment to verify an account
                        transaction.transaction_status = transaction.PENDING_BUYER
                    elif t['Status'] == 'Waiting for Payment by Payer and Recipient':
                        transaction.payment_status = transaction.PAYMENT_NOT_SENT
                        transaction.transaction_status = transaction.PAYMENT_PROCESSING
                    elif t['Status'] == 'Waiting for Payment by Recipient':
                        transaction.transaction_status = transaction.PENDING_ACC_SELLER
                        transaction.payment_status = transaction.FUNDS_IN_ESCROW
                    elif t['Status'] == 'Payer paid: Waiting for Recipient to Accept Terms':
                        transaction.transaction_status = transaction.PENDING_SELLER
                        transaction.payment_status = transaction.FUNDS_IN_ESCROW
                    elif t['Status'] == 'Voided':
                        transaction.transaction_status = transaction.VOIDED
                        transaction.payment_status = transaction.PAYMENT_NOT_SENT
                        transaction.transpact_scraped_datetime = make_aware(datetime.now())
                        transaction.save()
                    elif t['Status'] ==  'Waiting for Payment by Payer':
                        transaction.payment_status = transaction.PAYMENT_NOT_SENT
                        transaction.transaction_status = transaction.PAYMENT_PROCESSING
                    elif t['Status'] == 'Live and Protected: Waiting for instruction':
                        transaction.payment_status = transaction.FUNDS_IN_ESCROW
                        transaction.transaction_status = transaction.FUNDS_IN_ESCROW
                    elif t['Status'] == 'Transaction Completed':
                        transaction.payment_status = transaction.FUNDS_RELEASED
                        transaction.transaction_status = transaction.COMPLETED_ACK
                        transaction.product_status = transaction.PRODUCT_VERIFIED_OK
                        transaction.transpact_scraped_datetime = make_aware(datetime.now())
                        transaction.save()
                        tmp_user = transaction.user_passive.profile
                        tmp_user.user_successful_txns = tmp_user.user_successful_txns +1
                        tmp_user.save()
                        tmp_user = transaction.user_aggressive.profile
                        tmp_user.user_successful_txns = tmp_user.user_successful_txns +1
                        tmp_user.save()

                    elif t['Status'] == 'Arbitration Started: Waiting for Payment by Payer and Recipient':
                        tansaction.transacion_status = transaction.DISPUTE_REQUESTED

                # if transaction.transpact_text_status not in transpact_terminal_states:
                # TO_REVIEW: May create too many Historical records (will create for each scrape i think?)
                if transaction.transpact_text_status not in transpact_terminal_states:
                    transaction.transpact_scraped_datetime = make_aware(datetime.now())
                    transaction.save()


@shared_task
def createNewTransaction(txn_id):
    logging.info(f"create new transaction {txn_id}")
    txn = Transaction.objects.get(pk=txn_id)
    wsdl = settings.TRANSPACT_WSDL
    user = settings.TRANSPACT_PARTNER_USERNAME
    logging.info(f"username: {user}")

    password= settings.TRANSPACT_PARTNER_PASSWORD
    client = zeep.Client(wsdl=wsdl, service_name='Partner', port_name='PartnerSoap')
    if txn.order_passive.direction == 'B':
        buyer = txn.user_passive
        seller = txn.user_aggressive
    else:
        buyer = txn.user_aggressive
        seller = txn.user_passive

    total_px = txn.quantity * txn.price
    logging.error("new transaction : {} x {} = {}".format(total_px, txn.quantity, txn.price))
    sharing_hub_charge = 0
    escrow_fee = 0
    charges = txn.transactioncharge_set.all()
    for charge in charges:
        if charge.transaction_fee.slug == "escrow_fee":
            escrow_fee = charge.price
        elif charge.transaction_fee.slug == "sharing_hub_transaction_fee":
            sharing_hub_charge = charge.price
            total_px = total_px + charge.price
        else:
            total_px = total_px + charge.price
        
        logging.error("{}: {}".format(charge.transaction_fee.slug, charge.price))
        logging.error("total price: {}".format(total_px))
        

    with client.settings(raw_response=True):
        r = client.service.CreateTranspact(
           Username=user,
           Password=password,
           IsTest=settings.TRANSPACT_IS_TEST,
           NatureOfTransaction = 12,
           CreateType = 3,
           MoneySenderEmail = buyer.email,
           MoneyRecipientEmail = seller.email,
           Amount = round(total_px,2),
           Currency = 'GBP',
           TranspactNominatedReferee = True,
           Conditions = 'free text conditions',
           CanTransactorsChangeConditions = False,
           ConditionsConsumerClause = True,
           PartnerReference = txn.transaction_reference,
           MaxDaysDisputePayWait = 14,
           SenderFee = 5.98, #escrow_fee,
           RecipientFee = 0,
           OriginatorFee = 0,
           OriginatorFixedCommisionOnReceive = 0,
           OriginatorFixedCommisionAddBeforeStart = 0,
           OriginatorFixedCommisionOnSendToRcpnt = 0, #round(sharing_hub_charge,2),
           OriginatorFixedCommisionOnSendToAll = 0,
           OriginatorPcntCommisionOnReceive=0,
           OriginatorPcntCommisionOnSendToRcpnt=0,
           OriginatorPcntCommisionOnSendToAll=0,
           OriginatorPcntCommisionAddBeforeStart=0,
           CharityNo=zeep.xsd.Nil,
           IsFixedOnSendToRcpntFirst=False,
           PayerRealName=buyer.first_name,
           PayeeRealName=seller.first_name,
           )
        logging.error(r)

            # This section chooses if and how your fees and commissions are collected irrevocably from the transaction.
            # You can choose to collect your fee or commission at one or more of four events below, and for each event you can choose a percentage of the transaction amount or a fixed fee (or both).
            #
            # On Receive is the beginning of the transaction,when we receive payment. For marketing reasons, most of our partners avoid this option, and collet their fee at time of pay out.
            # On Receive is visible to both parties.
            # Fixed Commission on Receive:
            # Pcnt Commission on Receive:
            # On Send to All is collected at time of pay out.
            # It is visible to both parties.
            # Fixed Commission on Send to all:
            # Pcnt Commission on Send to all:
            # On Send to Payee is only collected if payout is made to the payee - if payment is made back to the payer, then no collection is made.
            # It is only visible to the Payee, and invisible to the Payer.
            # Fixed Commission on Send Payee:
            # Pcnt Commission on Send Payee:
            # Before Start is an amount added to the transaction amount, for the Payer to pay at the outset along with the transaction amount.
            # It is only visible to the Payer, and invisible to the Payee.


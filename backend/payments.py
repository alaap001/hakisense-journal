"""Provider boundary. Only this module knows Razorpay HTTP conventions."""
import httpx
from fastapi import HTTPException
from .config import config


class PaymentProvider:
    def __init__(self):
        self.client = httpx.Client(base_url='https://api.razorpay.com/v1/',
            auth=(config.razorpay_key, config.razorpay_secret), timeout=20,
            limits=httpx.Limits(max_connections=15, max_keepalive_connections=5))

    def request(self, method, path, **kwargs):
        if not config.razorpay_key or not config.razorpay_secret:
            raise HTTPException(503, 'Payments are temporarily unavailable.')
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise HTTPException(502, 'Payment confirmation is pending. Check billing before trying again.')
        if response.status_code >= 400:
            raise HTTPException(502, 'The payment provider could not complete this request. Please try again later.')
        return response.json()

    def payment(self, payment_id):
        return self.request('GET','payments/'+payment_id)

    def credit_link(self, purchase):
        return self.request('POST', 'payment_links', json={
            'amount':purchase.amount_paise, 'currency':'INR', 'accept_partial':False,
            'reference_id':purchase.id, 'description':f'{purchase.pack_name}: {purchase.credits} HakiSense credits',
            'notify':{'sms':False,'email':False}, 'reminder_enable':False,
            'expire_by':int(__import__('time').time())+1800,
            'notes':{'hakisense_purchase':purchase.id},
            'callback_url':config.origin.rstrip('/')+'/billing?payment=return', 'callback_method':'get'})

    def link(self, link_id):
        return self.request('GET', 'payment_links/'+link_id)

    def find_link(self, **query):
        rows = self.request('GET', 'payment_links', params=query).get('payment_links', [])
        return next((r for r in rows if not query.get('reference_id') or r.get('reference_id') == query['reference_id']), None)


provider = PaymentProvider()

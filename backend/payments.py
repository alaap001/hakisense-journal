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

    def subscription(self, subscription_id):
        return self.request('GET', 'subscriptions/' + subscription_id)

    def invoices(self, subscription_id):
        return self.request('GET', 'invoices', params={'subscription_id': subscription_id, 'count': 20})['items']

    def payment(self, payment_id):
        return self.request('GET', 'payments/' + payment_id)

    def plan(self, plan_id):
        return self.request('GET', 'plans/' + plan_id)

    def create_subscription(self, plan_id, interval, checkout_id, user_id):
        return self.request('POST', 'subscriptions', json={'plan_id': plan_id, 'quantity': 1,
            'total_count': 120 if interval == 'month' else 10, 'customer_notify': 1,
            'notes': {'hakisense_checkout': checkout_id, 'hakisense_user': user_id}})

    def cancel(self, subscription_id):
        return self.request('POST', 'subscriptions/' + subscription_id + '/cancel', json={'cancel_at_cycle_end': 1})


provider = PaymentProvider()

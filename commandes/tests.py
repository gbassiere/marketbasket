import datetime

from django.test import TestCase
from django.http import Http404
from django.urls import reverse
from django.db.models.query import QuerySet

from .models import Delivery, DeliveryLocation, CartItem, Cart
from .views import UserNameForm, CartItemForm

class CartTests(TestCase):

    def test_get_total(self):
        """Ensure get_total return the total price for this basket"""
        c = Cart()
        c.save()
        self.assertEqual(c.get_total(), 0)
        CartItem(cart=c, unit_price=2, quantity=2).save()
        self.assertEqual(c.get_total(), 4)
        CartItem(cart=c, unit_price=2.5, quantity=0.500).save()
        self.assertEqual(c.get_total(), 5.25)

class CartItemTests(TestCase):

    def test_custom_manager(self):
        """
        Ensure items are annotated with price computed from unit price x
        quantity
        """
        c = Cart()
        c.save()
        CartItem(cart=c, unit_price=2.5, quantity=0.500).save()
        i = c.items.first()
        self.assertTrue(hasattr(i, 'price'))
        self.assertEqual(i.price, 1.25)

class ViewTests(TestCase):
    fixtures = ['articles.json']

    def setUp(self):
        l = DeliveryLocation(name='Somewhere')
        l.save()
        d = datetime.date.today() + datetime.timedelta(days=3)
        self.delivery = Delivery(location=l,
                                 slot_date=d,
                                 slot_from=datetime.time(9, 0),
                                 slot_to=datetime.time(10, 0))
        self.delivery.save()

    def test_next_deliveries(self):
        response = self.client.get(reverse('next_deliveries'))
        self.assertIsInstance(response.context['deliveries'], QuerySet)
        self.assertIs(response.context['deliveries'].model, Delivery)
        self.assertEqual(response.status_code, 200)

    def test_needed_quantities(self):
        response = self.client.get(reverse('needed_quantities'))
        self.assertIn('deliveries', response.context)
        self.assertEqual(response.status_code, 200)

    def test_new_cart_get(self):
        response = self.client.get(reverse('new_cart', args=[self.delivery.id]))
        self.assertIn('user_form', response.context)
        self.assertIsInstance(response.context['user_form'], UserNameForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_new_cart_post(self):
        data = {'name': 'Johnny Haliday'}
        response = self.client.post(reverse('new_cart', args=[self.delivery.id]), data)
        c = Cart.objects.get(user=data['name'], delivery=self.delivery)
        self.assertRedirects(response, reverse('cart', args=[c.id]))

    def test_cart_get(self):
        # Trying to GET non-existing cart raises 404
        response = self.client.get(reverse('cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET a normal cart
        c = Cart(user='Johnny Haliday', delivery=self.delivery)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.assertIn('item_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_cart_post(self):
        c = Cart(user='Johnny Haliday', delivery=self.delivery)
        c.save()
        item_count = c.items.count()
        data = {'article': '1', 'quantity': '2.5'}
        response = self.client.post(reverse('cart', args=[c.id]), data)
        self.assertEqual(c.items.count(), item_count + 1)
        self.assertIn('item_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

import datetime

from django.test import TestCase
from django.http import Http404
from django.urls import reverse
from django.conf import settings
from django.db.models.query import QuerySet
from django.contrib.auth.models import User

from .models import Delivery, DeliveryLocation, CartItem, Cart, CartStatuses
from .views import CartItemForm

class CartTests(TestCase):
    fixtures = ['users.json']

    def test_get_total(self):
        """Ensure get_total return the total price for this basket"""
        francine = User.objects.get(username='francine')
        c = Cart(user=francine)
        c.save()
        self.assertEqual(c.get_total(), 0)
        CartItem(cart=c, unit_price=2, quantity=2).save()
        self.assertEqual(c.get_total(), 4)
        CartItem(cart=c, unit_price=2.5, quantity=0.500).save()
        self.assertEqual(c.get_total(), 5.25)

    def test_is_prepared(self):
        """ True when cart.status is prepared, False otherwise """
        francine = User.objects.get(username='francine')
        c = Cart(user=francine)
        self.assertFalse(c.is_prepared())
        c.status = CartStatuses.PREPARED
        self.assertTrue(c.is_prepared())
        c.status = CartStatuses.DELIVERED
        self.assertFalse(c.is_prepared())

class CartItemTests(TestCase):
    fixtures = ['users.json']

    def test_custom_manager(self):
        """
        Ensure items are annotated with price computed from unit price x
        quantity
        """
        francine = User.objects.get(username='francine')
        c = Cart(user=francine)
        c.save()
        CartItem(cart=c, unit_price=2.5, quantity=0.500).save()
        i = c.items.first()
        self.assertTrue(hasattr(i, 'price'))
        self.assertEqual(i.price, 1.25)

class ViewTests(TestCase):
    fixtures = ['articles.json', 'users.json', 'merchants.json']

    def setUp(self):
        l = DeliveryLocation(name='Somewhere')
        l.save()
        d = datetime.date.today() + datetime.timedelta(days=3)
        self.delivery = Delivery(location=l,
                                 slot_date=d,
                                 slot_from=datetime.time(9, 0),
                                 slot_to=datetime.time(10, 0))
        self.delivery.save()

    def test_merchant(self):
        response = self.client.get(reverse('merchant'))
        self.assertIn('deliveries', response.context)
        self.assertIn('contacts', response.context)
        self.assertIn('merchant', response.context)
        self.assertIsInstance(response.context['deliveries'], QuerySet)
        self.assertIs(response.context['deliveries'].model, Delivery)
        self.assertEqual(response.status_code, 200)

    def test_needed_quantities(self):
        path = reverse('needed_quantities')
        redirect_path = '%s?next=%s' % (settings.LOGIN_URL, path)
        # anonymous user
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        # authenticated user lacking permission (Francine is in Customer)
        self.client.login(username='francine', password='francine')
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        self.client.logout()
        # authenticated user with permission (Jerome is in Merchant)
        self.client.login(username='jerome', password='jerome')
        response = self.client.get(path)
        self.assertIn('deliveries', response.context)
        self.assertEqual(response.status_code, 200)

    def test_new_cart(self):
        path = reverse('new_cart', args=[self.delivery.id])
        redirect_path = '%s?next=%s' % (settings.LOGIN_URL, path)
        # anonymous user
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        # authenticated user with permission (Francine is in Customer)
        self.client.login(username='francine', password='francine')
        # Trying to GET non-existing delivery raises 404
        response = self.client.get(reverse('new_cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET with valid params
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)

    def test_cart_get(self):
        self.client.login(username='francine', password='francine')
        francine = User.objects.get(username='francine')
        reda = User.objects.get(username='reda')
        # Trying to GET non-existing cart raises 404
        response = self.client.get(reverse('cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET another user's cart
        c = Cart(user=reda, delivery=self.delivery)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.assertEqual(response.status_code, 302)
        # Trying to GET a normal cart
        c = Cart(user=francine, delivery=self.delivery)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.assertIn('item_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_cart_post(self):
        self.client.login(username='francine', password='francine')
        francine = User.objects.get(username='francine')
        c = Cart(user=francine, delivery=self.delivery)
        c.save()
        item_count = c.items.count()
        data = {'article': '1', 'quantity': '2.5'}
        response = self.client.post(reverse('cart', args=[c.id]), data)
        self.assertEqual(c.items.count(), item_count + 1)
        self.assertIn('item_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_prepare_baskets(self):
        path = reverse('prepare_baskets', args=[self.delivery.id])
        redirect_path = '%s?next=%s' % (settings.LOGIN_URL, path)
        # anonymous user
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        # authenticated user lacking permission (Francine is in Customer)
        self.client.login(username='francine', password='francine')
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        self.client.logout()
        # authenticated user with permission
        self.client.login(username='reda', password='reda')
        # Trying to GET non-existing delivery raises 404
        response = self.client.get(reverse('prepare_baskets', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET a normal delivery
        response = self.client.get(path)
        self.assertIn('delivery', response.context)
        self.assertEqual(response.status_code, 200)
        # Trying to POST a delivered cart
        francine = User.objects.get(username='francine')
        c = Cart(user=francine, delivery=self.delivery)
        c.save()
        data = {'delivered_cart': c.id}
        response = self.client.post(path, data)
        c.refresh_from_db()
        self.assertEqual(c.status, CartStatuses.DELIVERED)
        self.assertEqual(response.status_code, 200)

    def test_prepare_basket(self):
        francine = User.objects.get(username='francine')
        c = Cart(user=francine, delivery=self.delivery)
        c.save()
        path = reverse('prepare_basket', args=[c.id])
        redirect_path = '%s?next=%s' % (settings.LOGIN_URL, path)
        # anonymous user
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        # authenticated user lacking permission (Francine is in Customer)
        self.client.login(username='francine', password='francine')
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        self.client.logout()
        # authenticated user with permission
        self.client.login(username='reda', password='reda')
        # Trying to GET non-existing delivery raises 404
        response = self.client.get(reverse('prepare_basket', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET a normal delivery
        response = self.client.get(path)
        self.assertIn('basket', response.context)
        self.assertEqual(c.status, CartStatuses.RECEIVED)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(path, {'start': ''})
        self.assertIn('basket', response.context)
        c.refresh_from_db()
        self.assertEqual(c.status, CartStatuses.PREPARING)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(path, {'ready': ''})
        c.refresh_from_db()
        self.assertEqual(c.status, CartStatuses.PREPARED)
        self.assertEqual(response.status_code, 302)

import datetime
from functools import reduce

from django.test import TestCase
from django.http import Http404
from django.urls import reverse
from django.conf import settings
from django.db.models.query import QuerySet
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Delivery, DeliveryLocation, DeliverySlot, \
                    UnitTypes, \
                    CartItem, Cart, CartStatuses
from .views import CartItemForm, AnnotationForm

class DeliveryTests(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        # Create a delivery place
        l = DeliveryLocation(name='Somewhere')
        l.save()
        # then the delivery itself
        self.delivery = Delivery(location=l)
        self.delivery.save()
        # then a time slot for this delivery
        tz = timezone.utc
        d1 = datetime.datetime.combine(
                    datetime.date.today() + datetime.timedelta(days=3),
                    datetime.time(7, 0, tzinfo=tz))
        d2 = d1 + datetime.timedelta(hours=2)
        self.slot = DeliverySlot(delivery=self.delivery, start=d1, end=d2)
        self.slot.save()

    def test_get_active_carts_by_slot(self):
        francine = User.objects.get(username='francine')
        interval = 30
        start = self.slot.start
        kwargs = {'delivery': self.delivery}
        self.slot.delete()
        cart_count = 0
        for i in range(4): # 4 slots (30' within 2h)
            kwargs['start'] = start + datetime.timedelta(minutes=i*interval)
            kwargs['end'] = start + datetime.timedelta(minutes=(i+1)*interval)
            s = DeliverySlot(**kwargs)
            s.save()
            for j in range(1 + i%2): # 1 or 2 carts by slots, 6 in total
                Cart(user=francine, slot=s).save()
                cart_count += 1
        res = self.delivery.get_active_carts_by_slot()
        self.assertEqual(self.delivery.slots.count(), len(res))
        self.assertEqual(cart_count,
                         reduce(lambda x, y: x+len(y['baskets']), res, 0))

    def test_get_needed_quantities(self):
        francine = User.objects.get(username='francine')
        reda = User.objects.get(username='reda')
        # No data, should return an empty queryset
        qs1 = self.delivery.get_needed_quantities()
        self.assertEqual(qs1.count(), 0)
        # A Cart exists but no CartItem, should return an empty queryset
        c1 = Cart(user=francine, slot=self.slot)
        c1.save()
        qs2 = self.delivery.get_needed_quantities()
        self.assertEqual(qs2.count(), 0)
        # One cart exist with one cartItem
        kwargs = {'cart': c1, 'label': 'xxx', 'unit_price': 2.5,
                        'unit_type': UnitTypes.WEIGHT, 'quantity': 0.500}
        CartItem(**kwargs).save()
        qs3 = self.delivery.get_needed_quantities()
        self.assertEqual(qs3.count(), 1)
        self.assertEqual(qs3[0]['quantity'], 0.5)
        # Two Cart with the same CartItem
        c2 = Cart(user=reda, slot=self.slot)
        c2.save()
        kwargs['cart'] = c2
        CartItem(**kwargs).save()
        qs4 = self.delivery.get_needed_quantities()
        self.assertEqual(qs4.count(), 1)
        self.assertEqual(qs4[0]['quantity'], 1)
        # Add a different CartItem
        kwargs['label'] = 'yyy'
        CartItem(**kwargs).save()
        qs5 = self.delivery.get_needed_quantities()
        self.assertEqual(qs5.count(), 2)

class CartTests(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        # Retrieve Francine
        self.francine = User.objects.get(username='francine')
        # Create a delivery place
        l = DeliveryLocation(name='Somewhere')
        l.save()
        # then the delivery itself
        self.delivery = Delivery(location=l)
        self.delivery.save()
        # then a time slot for this delivery
        tz = timezone.utc
        d1 = datetime.datetime.combine(
                    datetime.date.today() + datetime.timedelta(days=3),
                    datetime.time(7, 0, tzinfo=tz))
        d2 = d1 + datetime.timedelta(hours=2)
        self.slot = DeliverySlot(delivery=self.delivery, start=d1, end=d2)
        self.slot.save()
        # then a cart on this slot for Francine
        self.cart = Cart(user=self.francine, slot=self.slot)
        self.cart.save()

    def test_get_total(self):
        """Ensure get_total return the total price for this basket"""
        self.assertEqual(self.cart.get_total(), 0)
        CartItem(cart=self.cart, unit_price=2, quantity=2).save()
        self.assertEqual(self.cart.get_total(), 4)
        CartItem(cart=self.cart, unit_price=2.5, quantity=0.500).save()
        self.assertEqual(self.cart.get_total(), 5.25)

    def test_is_prepared(self):
        """ True when cart.status is prepared, False otherwise """
        self.cart = Cart(user=self.francine, slot=self.slot)
        self.assertFalse(self.cart.is_prepared())
        self.cart.status = CartStatuses.PREPARED
        self.assertTrue(self.cart.is_prepared())
        self.cart.status = CartStatuses.DELIVERED
        self.assertFalse(self.cart.is_prepared())

class CartItemTests(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        # Retrieve Francine
        francine = User.objects.get(username='francine')
        # Create a delivery place
        l = DeliveryLocation(name='Somewhere')
        l.save()
        # then the delivery itself
        self.delivery = Delivery(location=l)
        self.delivery.save()
        # then a time slot for this delivery
        tz = timezone.utc
        d1 = datetime.datetime.combine(
                    datetime.date.today() + datetime.timedelta(days=3),
                    datetime.time(7, 0, tzinfo=tz))
        d2 = d1 + datetime.timedelta(hours=2)
        s = DeliverySlot(delivery=self.delivery, start=d1, end=d2)
        s.save()
        # then a cart on this slot for Francine
        self.cart = Cart(user=francine, slot=s)
        self.cart.save()

    def test_custom_manager(self):
        """
        Ensure items are annotated with price computed from unit price x
        quantity
        """
        CartItem(cart=self.cart, unit_price=2.5, quantity=0.500).save()
        i = self.cart.items.first()
        self.assertTrue(hasattr(i, 'price'))
        self.assertEqual(i.price, 1.25)

class ViewTests(TestCase):
    fixtures = ['articles.json', 'users.json', 'merchants.json']

    def setUp(self):
        # Create a delivery place
        l = DeliveryLocation(name='Somewhere')
        l.save()
        # then the delivery itself
        self.delivery = Delivery(location=l)
        self.delivery.save()
        # then a time slot for this delivery
        tz = timezone.utc
        d1 = datetime.datetime.combine(
                    datetime.date.today() + datetime.timedelta(days=3),
                    datetime.time(7, 0, tzinfo=tz))
        d2 = d1 + datetime.timedelta(hours=2)
        self.slot = DeliverySlot(delivery=self.delivery, start=d1, end=d2)
        self.slot.save()

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

    def cart_final_tests(self, response):
        self.assertIn('item_form', response.context)
        self.assertIn('annot_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIsInstance(response.context['annot_form'], AnnotationForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_cart_get(self):
        self.client.login(username='francine', password='francine')
        francine = User.objects.get(username='francine')
        reda = User.objects.get(username='reda')
        # Trying to GET non-existing cart raises 404
        response = self.client.get(reverse('cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET another user's cart
        c = Cart(user=reda, slot=self.slot)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.assertEqual(response.status_code, 302)
        # Trying to GET a normal cart
        c = Cart(user=francine, slot=self.slot)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.cart_final_tests(response)
        # SlotForm not enabled when there's a single time slot
        self.assertNotIn('slot_form', response.context)
        DeliverySlot(delivery=self.delivery, start=self.slot.end,
                    end=self.slot.end + datetime.timedelta(minutes=30)).save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.cart_final_tests(response)
        self.assertIn('slot_form', response.context)

    def test_cart_post(self):
        self.client.login(username='francine', password='francine')
        francine = User.objects.get(username='francine')
        c = Cart(user=francine, slot=self.slot)
        c.save()
        path = reverse('cart', args=[c.id])
        # invalid post
        data = {'article': '1', 'quantity': '2.5'}
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 400)
        # post an item
        item_count = c.items.count()
        data = {'article': '1', 'quantity': '2.5', 'item_submit': ''}
        response = self.client.post(path, data)
        self.assertEqual(c.items.count(), item_count + 1)
        self.cart_final_tests(response)
        # post an item to be deleted
        data = {'del_submit': c.items.first().id}
        response = self.client.post(path, data)
        self.assertEqual(c.items.count(), item_count)
        self.cart_final_tests(response)
        # post a time slot
        self.slot.end = self.slot.start + datetime.timedelta(minutes=30)
        self.slot.save()
        self.assertEqual(c.slot, self.slot)
        new_slot =  DeliverySlot(delivery=self.delivery, start=self.slot.end,
                    end=self.slot.end + datetime.timedelta(minutes=30))
        new_slot.save()
        data = {'slot': new_slot.id, 'slot_submit': ''}
        response = self.client.post(path, data)
        c.refresh_from_db()
        self.assertEqual(new_slot, c.slot)
        # post an annotation
        self.assertEqual(c.annotation, '')
        data = {'annotation': 'bla', 'annot_submit': ''}
        response = self.client.post(path, data)
        c.refresh_from_db()
        self.assertEqual(c.annotation, 'bla')
        self.cart_final_tests(response)

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
        c = Cart(user=francine, slot=self.slot)
        c.save()
        data = {'delivered_cart': c.id}
        response = self.client.post(path, data)
        c.refresh_from_db()
        self.assertEqual(c.status, CartStatuses.DELIVERED)
        self.assertEqual(response.status_code, 200)

    def test_prepare_basket(self):
        francine = User.objects.get(username='francine')
        c = Cart(user=francine, slot=self.slot)
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

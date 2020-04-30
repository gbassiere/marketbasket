import datetime
from decimal import Decimal
from functools import reduce

from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Delivery, DeliveryLocation, DeliverySlot, \
                    UnitTypes, \
                    CartItem, Cart, CartStatuses
from .forms import CartItemForm, AnnotationForm, SlotSelect, SlotForm
from .admin import DeliverySlotForm


class BasketTestCase(TestCase):
    """
    Base class testing MarketBasket code. Does not hold any test case. Only
    code that is shared across test cases (initialization code).
    """

    fixtures = ['users.json']

    def install_user(self, username):
        "Retrieve a testing user from database"
        setattr(self, username, User.objects.get(username=username))

    def install_delivery(self, where='Somewhere'):
        "Create testing instance of DeliveryLocation and Delivery"
        l = DeliveryLocation(name=where)
        l.save()
        self.delivery = Delivery(location=l)
        self.delivery.save()

    def install_slots(self, delta_days, start, interval, number):
        """
        Create as many slots as specified:
        - delta_days (int): start that many days after (or before if
          negative) today
        - start (int): first slot will start at that hour
        - interval (int): each slot last that many minutes
        - number (int): create that many slots
        """
        tz = timezone.utc
        d = datetime.datetime.combine(
                   datetime.date.today() + datetime.timedelta(days=delta_days),
                   datetime.time(start, 0, tzinfo=tz))
        for i in range(number):
            ds = d + datetime.timedelta(minutes=i*interval)
            de = d + datetime.timedelta(minutes=(i+1)*interval)
            s = DeliverySlot(delivery=self.delivery, start=ds, end=de)
            s.save()
            setattr(self, 'slot%d' % (i+1), s)


class UnitTypesTests(TestCase):
    """
    Test case for UnitTypes which is a mere TextChoices but have a custom
    method.
    """
    def test_hr_quantity(self):
        with self.assertRaises(ValueError):
            UnitTypes.UNIT.hr_quantity('a string')
        values = (1, 1.0, 3, 3.0, Decimal(1.0), Decimal(3))
        for value in values:
            self.assertRegex(UnitTypes.UNIT.hr_quantity(value), r'^\d+')
        for value in values + (1.5, 5.43, Decimal(1.555)):
            self.assertRegex(UnitTypes.WEIGHT.hr_quantity(value),
                                                            r'^\d+\.?\d* ')
        for value in (0.555, Decimal(.6), .7):
            self.assertRegex(UnitTypes.WEIGHT.hr_quantity(value),
                                                            r'^\d{3} ')


class SlotSelectTests(TestCase):
    """
    Test case for SlotSelect which a Select widget with special behaviour for
    disabled options
    """

    def test_create_option(self):
        w = SlotSelect()
        lbl = 'label'
        # if label doesn't end with '[*]', a normal option is created
        opt = w.create_option('name', 1, lbl, False, 1, None, {})
        self.assertEqual(lbl, opt['label'])
        self.assertNotIn('disabled', opt['attrs'])
        # if label ends with '[*]' the created option is disabled
        opt = w.create_option('name', 1, lbl+'[*]', False, 1, None, {})
        self.assertEqual(lbl, opt['label'])
        self.assertIn('disabled', opt['attrs'])


class SlotFormTests(BasketTestCase):
    """
    Test case for SlotForm which let a user choose his delivery slot.
    """

    def setUp(self):
        self.install_user('francine')
        self.install_delivery()
        self.install_slots(3, 7, 60, 2)

    def test_form_init(self):
        f = SlotForm(initial={'slot': self.slot1})
        # queryset should be properly annotated
        slot = f.fields['slot'].queryset.first()
        self.assertTrue(hasattr(slot, 'cart_count'))

    def test_clean_slot(self):
        # Ensure cart_count <= max_per_slot if max_per_slot > 0
        # The form should not behave exactly the same way when post data is
        # initial data, this case is alse explicitly tested.
        data = {'slot': self.slot1.id, 'slot_submit': ''}
        # max_per_slot = 0 (disabled) and cart_count = 0, no ValidationError
        f = SlotForm(data, initial={'slot': self.slot1})
        f.is_valid()
        self.assertEqual(f.clean_slot(), self.slot1)
        data['slot'] = self.slot2.id
        f = SlotForm(data, initial={'slot': self.slot1})
        f.is_valid()
        self.assertEqual(f.clean_slot(), self.slot2)
        # max_per_slot = 1 and cart_count = 0, no ValidationError
        self.delivery.max_per_slot = 1
        f = SlotForm(data, initial={'slot': self.slot1})
        f.is_valid()
        self.assertEqual(f.clean_slot(), self.slot2)
        data['slot'] = self.slot1.id
        f = SlotForm(data, initial={'slot': self.slot1})
        f.is_valid()
        self.assertEqual(f.clean_slot(), self.slot1)
        # max_per_slot = 1 and cart_count = 1, ValidationError!
        Cart(user=self.francine, slot=self.slot1).save()
        Cart(user=self.francine, slot=self.slot2).save()
        f = SlotForm(data, initial={'slot': self.slot1})
        self.assertTrue(f.is_valid()) # True because data == initial
        data['slot'] = self.slot2.id
        f = SlotForm(data, initial={'slot': self.slot1})
        self.assertFalse(f.is_valid())

    def test_label_from_instance(self):
        f = SlotForm(initial={'slot': self.slot1})
        field = f.fields['slot']
        # max_per_slot = 0 (disabled) and cart_count = 0
        slot = field.queryset.first()
        lbl = field.label_from_instance(slot)
        self.assertFalse(lbl.endswith('[*]'))
        # max_per_slot = 1 and cart_count = 0
        self.delivery.max_per_slot = 1
        lbl = field.label_from_instance(slot)
        self.assertFalse(lbl.endswith('[*]'))
        # max_per_slot = 1 and cart_count = 1
        Cart(user=self.francine, slot=self.slot1).save()
        slot = field.queryset.filter(id=self.slot1.id).first() # QS refresh
        lbl = field.label_from_instance(slot)
        self.assertTrue(lbl.endswith('[*]'))


class SlotFormTests(BasketTestCase):
    """
    Test case for SlotForm (admin form), provide custom validation
    """

    def setUp(self):
        self.install_user('francine')
        self.install_delivery()
        self.install_slots(3, 7, 60, 1)

    def test_clean(self):
        s = self.slot1
        valid_end = s.end + datetime.timedelta(hours=1)
        invalid_end = s.start - datetime.timedelta(hours=1)
        # test with invalid end (end < start)
        data = {'start': s.start, 'end': invalid_end, 'delivery': self.delivery}
        self.assertFalse(DeliverySlotForm(data, instance=s).is_valid())
        # test with valid end (end >= start)
        data['end'] = valid_end
        self.assertTrue(DeliverySlotForm(data, instance=s).is_valid())
        # editing a slot which already have carts should not be possible
        Cart(user=self.francine, slot=s).save()
        self.assertFalse(DeliverySlotForm(data, instance=s).is_valid())


class DeliveryTests(BasketTestCase):
    """
    Test case for Delivery model.
    """

    def setUp(self):
        self.install_user('francine')
        self.install_user('reda')
        self.install_delivery()

    def test_get_active_carts_by_slot(self):
        kwargs = {'delivery': self.delivery}
        cart_count = 0
        self.install_slots(3, 7, 30, 4) # 4 slots (30' within 2h)
        for i in range(4):
            s = getattr(self, 'slot%d' % (i+1))
            for j in range(1 + i%2): # 1 or 2 carts by slots, 6 in total
                Cart(user=self.francine, slot=s).save()
                cart_count += 1
        res = self.delivery.get_active_carts_by_slot()
        self.assertEqual(self.delivery.slots.count(), len(res))
        self.assertEqual(cart_count,
                         reduce(lambda x, y: x+len(y['baskets']), res, 0))

    def test_get_needed_quantities(self):
        self.install_slots(3, 7, 120, 1)
        # No data, should return an empty queryset
        qs1 = self.delivery.get_needed_quantities()
        self.assertEqual(qs1.count(), 0)
        # A Cart exists but no CartItem, should return an empty queryset
        c1 = Cart(user=self.francine, slot=self.slot1)
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
        c2 = Cart(user=self.reda, slot=self.slot1)
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

class CartTests(BasketTestCase):
    """
    Test case for Cart model.
    """

    def setUp(self):
        self.install_user('francine')
        self.install_delivery()
        self.install_slots(3, 7, 120, 1)
        self.cart = Cart(user=self.francine, slot=self.slot1)
        self.cart.save()

    def test_get_total(self):
        """ Ensure get_total return the total price for this basket """
        self.assertEqual(self.cart.get_total(), 0)
        CartItem(cart=self.cart, unit_price=2, quantity=2).save()
        self.assertEqual(self.cart.get_total(), 4)
        CartItem(cart=self.cart, unit_price=2.5, quantity=0.500).save()
        self.assertEqual(self.cart.get_total(), 5.25)

    def test_is_prepared(self):
        """ True when cart.status is prepared, False otherwise """
        self.assertFalse(self.cart.is_prepared())
        self.cart.status = CartStatuses.PREPARED
        self.assertTrue(self.cart.is_prepared())
        self.cart.status = CartStatuses.DELIVERED
        self.assertFalse(self.cart.is_prepared())

class CartItemTests(BasketTestCase):
    """
    Test case for CartItem model.
    """

    def setUp(self):
        self.install_user('francine')
        self.install_delivery()
        self.install_slots(3, 7, 120, 1)
        self.cart = Cart(user=self.francine, slot=self.slot1)
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

class ViewTests(BasketTestCase):
    """
    Test case for views
    """
    fixtures = ['articles.json', 'users.json', 'merchants.json']

    def setUp(self):
        self.install_user('francine')
        self.install_user('reda')
        self.install_delivery()
        self.install_slots(3, 7, 120, 1)

    def test_merchant(self):
        """
        Merchant view
        """
        # response context has necessary data (cart limit disabled)
        response = self.client.get(reverse('merchant'))
        self.assertIn('deliveries', response.context)
        self.assertIn('contacts', response.context)
        self.assertIn('merchant', response.context)
        self.assertEqual(response.status_code, 200)
        # enable cart limit and test is_full proper computation
        self.delivery.max_per_slot = 1
        self.delivery.save()
        response = self.client.get(reverse('merchant'))
        self.assertFalse(response.context['deliveries'][0]['is_full'])
        Cart(user=self.francine, slot=self.slot1).save()
        response = self.client.get(reverse('merchant'))
        self.assertTrue(response.context['deliveries'][0]['is_full'])


    def test_needed_quantities(self):
        """
        Needed quantities view
        """
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
        """
        New cart view
        """
        path = reverse('new_cart', args=[self.delivery.id])
        redirect_path = '%s?next=%s' % (settings.LOGIN_URL, path)
        error_path = reverse('merchant')
        # anonymous user
        response = self.client.get(path)
        self.assertRedirects(response, redirect_path)
        # authenticated user with permission (Francine is in Customer)
        self.client.login(username='francine', password='francine')
        # Trying to GET non-existing delivery raises 404
        response = self.client.get(reverse('new_cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET with valid params (cart limit disabled)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, error_path)
        # Trying to GET with valid params (cart limit enabled)
        self.delivery.max_per_slot = 2 # 1 slot with 1 cart created above
        self.delivery.save()
        response = self.client.get(path) # second cart should pass
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, error_path)
        response = self.client.get(path) # third cart should fail
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, error_path)


    def cart_final_tests(self, response):
        """ Helper method for testing context returned by cart view """
        self.assertIn('item_form', response.context)
        self.assertIn('annot_form', response.context)
        self.assertIsInstance(response.context['item_form'], CartItemForm)
        self.assertIsInstance(response.context['annot_form'], AnnotationForm)
        self.assertIn('cart', response.context)
        self.assertEqual(response.status_code, 200)

    def test_cart_get(self):
        """
        Cart view (called with GET method)
        """
        self.client.login(username='francine', password='francine')
        # Trying to GET non-existing cart raises 404
        response = self.client.get(reverse('cart', args=[0]))
        self.assertEqual(response.status_code, 404)
        # Trying to GET another user's cart
        c = Cart(user=self.reda, slot=self.slot1)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.assertEqual(response.status_code, 302)
        # Trying to GET a normal cart
        c = Cart(user=self.francine, slot=self.slot1)
        c.save()
        response = self.client.get(reverse('cart', args=[c.id]))
        self.cart_final_tests(response)
        # SlotForm not enabled when there's a single time slot
        self.assertNotIn('slot_form', response.context)
        self.install_slots(3, 9, 120, 1)
        response = self.client.get(reverse('cart', args=[c.id]))
        self.cart_final_tests(response)
        self.assertIn('slot_form', response.context)

    def test_cart_post(self):
        """
        Cart view (called with POST method)
        """
        self.client.login(username='francine', password='francine')
        c = Cart(user=self.francine, slot=self.slot1)
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
        old_slot = self.slot1
        self.assertEqual(c.slot, old_slot)
        self.install_slots(3, 9, 120, 1)
        new_slot = self.slot1
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
        """
        Prepare baskets view (list all baskets to be prepared)
        """
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
        c = Cart(user=self.francine, slot=self.slot1)
        c.save()
        data = {'delivered_cart': c.id}
        response = self.client.post(path, data)
        c.refresh_from_db()
        self.assertEqual(c.status, CartStatuses.DELIVERED)
        self.assertEqual(response.status_code, 200)

    def test_prepare_basket(self):
        """
        Prepare basket view (show one basket to be prepared)
        """
        c = Cart(user=self.francine, slot=self.slot1)
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

from miro.test import mock
from miro.test.framework import MiroTestCase
from miro.frontends.widgets import cellpack

class LayoutTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.context = mock.Mock()
        self.drawer = mock.Mock()

    def make_simple_layout(self):
        layout = cellpack.Layout()
        layout.add(0, 0, 200, 200, self.drawer.background)
        layout.add(0, 0, 50, 50, self.drawer.foo)
        layout.add_rect(cellpack.LayoutRect(50, 0, 30, 30),
                self.drawer.right_of_foo, hotspot='right_of_foo')
        layout.add_rect(cellpack.LayoutRect(0, 50, 30, 30),
                self.drawer.under_foo, hotspot='under_foo')
        return layout

    def test_simple(self):
        # check if layout.draw() calls the correct methods
        layout = self.make_simple_layout()
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('background', (self.context, 0, 0, 200, 200)),
                ('foo', (self.context, 0, 0, 50, 50)),
                ('right_of_foo', (self.context, 50, 0, 30, 30)),
                ('under_foo', (self.context, 0, 50, 30, 30)),
        ])
        self.assertEquals(layout.last_rect,
                cellpack.LayoutRect(0, 50, 30, 30))

    def test_merge(self):
        # check merging in a second layout
        layout1 = self.make_simple_layout()
        layout2 = cellpack.Layout()
        layout2.add(50, 50, 50, 50, self.drawer.merged)
        layout1.merge(layout2)
        layout1.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('background', (self.context, 0, 0, 200, 200)),
                ('foo', (self.context, 0, 0, 50, 50)),
                ('right_of_foo', (self.context, 50, 0, 30, 30)),
                ('under_foo', (self.context, 0, 50, 30, 30)),
                ('merged', (self.context, 50, 50, 50, 50)),
        ])
        self.assertEquals(layout1.last_rect, layout2.last_rect)

    def test_center(self):
        # check centering inside a layout
        layout = cellpack.Layout()
        layout.add(0, 0, 50, 50, self.drawer.foo)
        layout.add(55, 0, 30, 30, self.drawer.bar)

        # y-center #1 elements should be centered around y=25
        layout.center_y(top=0)
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('foo', (self.context, 0, 0, 50, 50)),
                ('bar', (self.context, 55, 10, 30, 30))])
        # y-center #2 elements should be centered around y=60
        self.drawer.reset_mock()
        layout.center_y(top=10, bottom=110)
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('foo', (self.context, 0, 35, 50, 50)),
                ('bar', (self.context, 55, 45, 30, 30))])
        # x-center #1 elements should be centered around x=50
        self.drawer.reset_mock()
        layout = cellpack.Layout()
        layout.add(0, 0, 50, 50, self.drawer.foo)
        layout.add(0, 50, 100, 50, self.drawer.bar)
        layout.center_x(left=0)
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('foo', (self.context, 25, 0, 50, 50)),
                ('bar', (self.context, 0, 50, 100, 50))])
        # x-center #2 elements should be centered with x=60 in the middle
        self.drawer.reset_mock()
        layout.center_x(left=50, right=70)
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('foo', (self.context, 35, 0, 50, 50)),
                ('bar', (self.context, 10, 50, 100, 50))]),

    def test_alter_returned_rect(self):
        # test altering a LayoutRect after it's been returned by the add
        # method
        layout = cellpack.Layout()
        rect = layout.add(0, 0, 0, 0, self.drawer.altered)
        rect.x = 50
        rect.width = 100
        rect.height = 200
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls,
                [('altered', (self.context, 50, 0, 100, 200))])

    def test_translate(self):
        # test translating layouts
        layout = self.make_simple_layout()
        layout.translate(50, 25)
        layout.draw(self.context)
        self.assertSameList(self.drawer.method_calls, [
                ('background', (self.context, 50, 25, 200, 200)),
                ('foo', (self.context, 50, 25, 50, 50)),
                ('right_of_foo', (self.context, 100, 25, 30, 30)),
                ('under_foo', (self.context, 50, 75, 30, 30)),
        ])

    def test_hotspot(self):
        # test finding hotspots
        layout = self.make_simple_layout()
        self.assertEquals(layout.find_hotspot(50, 0), ('right_of_foo', 0, 0))
        self.assertEquals(layout.find_hotspot(60, 15),
                ('right_of_foo', 10, 15))
        self.assertEquals(layout.find_hotspot(0, 0), None)
        self.assertEquals(layout.find_hotspot(0, 50), ('under_foo', 0, 0))
        self.assertEquals(layout.find_hotspot(29, 79), ('under_foo', 29, 29))
        self.assertEquals(layout.find_hotspot(30, 79), None)
        self.assertEquals(layout.find_hotspot(29, 80), None)

    def test_add_text_line(self):
        layout = cellpack.Layout()
        textbox = mock.Mock()
        textbox.font.line_height.return_value = 30
        layout.add_text_line(textbox, 100, 100, 50)
        layout.draw(self.context)
        textbox.draw.assert_called_with(self.context, 100, 100, 50, 30)

    def test_add_image(self):
        layout = cellpack.Layout()
        image = mock.Mock()
        image.get_size.return_value = (20, 50)
        layout.add_image(image, 100, 100)
        layout.draw(self.context)
        image.draw.assert_called_with(self.context, 100, 100, 20, 50)

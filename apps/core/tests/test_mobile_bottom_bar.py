"""
# // ==============================================================================
# // KCC CLASSSTAMP - MOBILE BOTTOM BAR CLEARANCE
# // ==============================================================================
# // The phone layout uses a fixed 62px tab bar. A later global
# // `.main-content { padding: 16px 20px !important }` rule once reset the bottom
# // padding to 16px at every width, so the last control on a page (the profile's
# // "Update Password" button) sat underneath the bar with no way to scroll to it.
# //
# // This guard keeps the winning `.main-content` padding rule inside the mobile
# // media query and tall enough to clear the bar.
# // ==============================================================================
"""

import pathlib
import re

from django.test import SimpleTestCase

REFINE_CSS = pathlib.Path('static/css/refine.css')
TAB_BAR_HEIGHT = 62          # measured .mobile-bottom-nav height
MIN_CLEARANCE = 80           # bar + breathing room


class MobileBottomBarClearanceTests(SimpleTestCase):

    def _rules(self):
        css = REFINE_CSS.read_text(encoding='utf-8')
        pattern = re.compile(r'\.main-content\s*\{[^}]*?padding\s*:[^;]+;', re.I)
        return css, list(pattern.finditer(css))

    def test_last_main_content_padding_rule_clears_the_tab_bar(self):
        css, matches = self._rules()
        self.assertTrue(matches, 'no .main-content padding rule found in refine.css')

        last = matches[-1]
        rule = last.group(0)
        numbers = [int(value) for value in re.findall(r'(\d+)px', rule)]
        self.assertTrue(numbers, f'could not read a pixel value from {rule!r}')

        if len(numbers) >= 4:      # top right bottom left
            bottom = numbers[2]
        else:                      # one or two values: vertical is first
            bottom = numbers[0]

        self.assertGreaterEqual(
            bottom, MIN_CLEARANCE,
            f'the final .main-content rule must keep >= {MIN_CLEARANCE}px under the '
            f'{TAB_BAR_HEIGHT}px tab bar, found {bottom}px: {rule!r}',
        )

    def test_the_winning_rule_is_scoped_to_phones(self):
        css, matches = self._rules()
        last = matches[-1]
        # Walk back to the nearest @media block that is still open at this point.
        before = css[:last.start()]
        media_positions = [m.end() for m in re.finditer(r'@media[^{]+\{', before)]
        self.assertTrue(media_positions, 'the rule is not inside a media query')

        tail = before[media_positions[-1]:]
        # A still-open media query has no closing brace before the rule.
        self.assertNotIn('}', tail, 'the rule is outside the media query')
        media_query = before[max(0, media_positions[-1] - 120):media_positions[-1]]
        self.assertIn(
            'max-width: 900px', media_query,
            f'the winning padding rule must apply to phones, found: {media_query!r}',
        )

    def test_bundle_order_keeps_the_clearance_last(self):
        """The generated bundle must ship the clearance after the global reset."""
        bundle = pathlib.Path('static/css/classstamp.bundle.css')
        if not bundle.exists():          # generated + gitignored; skip when absent
            self.skipTest('bundle not built')
        css = bundle.read_text(encoding='utf-8', errors='ignore')
        reset = css.find('.main-content {\n  padding: 16px 20px !important;')
        clearance = css.rfind('padding: 16px 14px 96px 14px !important')
        self.assertNotEqual(reset, -1, 'global padding reset rule disappeared')
        self.assertNotEqual(clearance, -1, 'mobile clearance rule missing from the bundle')
        self.assertGreater(
            clearance, reset,
            'the mobile clearance must be bundled AFTER the global padding reset',
        )

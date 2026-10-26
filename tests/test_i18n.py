import re

from pyatnitsa import i18n


def test_every_template_has_identical_placeholders_in_all_three_languages():
    for key, variants in i18n._S.items():
        sets = [set(re.findall(r"\{(\w+)(?::[^}]*)?\}", v)) for v in variants]
        assert sets[0] == sets[1] == sets[2], (key, sets)


def test_templates_format_without_errors_given_their_placeholders():
    for key, variants in i18n._S.items():
        for v in variants:
            names = set(re.findall(r"\{(\w+)(?::[^}]*)?\}", v))
            kw = {n: 1.0 if re.search(r"\{%s:[^}]*[fd]" % n, v) else "x" for n in names}
            v.format(**kw)                                   # KeyError / ValueError bo'lsa test yiqiladi


def test_placeholder_named_lang_is_never_used_because_T_takes_lang_positionally():
    assert not any("{lang}" in v for variants in i18n._S.values() for v in variants)


def test_unknown_language_falls_back_to_uzbek_and_unknown_key_returns_the_key():
    assert i18n.T("cancelled", "xx") == i18n.T("cancelled", "uz") and i18n.T("no.such.key") == "no.such.key"

from pyatnitsa.i18n import voice_name
from pyatnitsa.settings import Settings


def test_default_voice_is_male_for_every_language():
    assert Settings().voice_gender == "male"
    assert [voice_name("male", l) for l in ("uz", "ru", "en")] == ["uz-UZ-SardorNeural", "ru-RU-DmitryNeural", "en-US-GuyNeural"]


def test_female_voice_still_selectable_and_bad_value_falls_back_to_male(tmp_path):
    assert voice_name("female", "uz") == "uz-UZ-MadinaNeural"
    p = tmp_path / "s.json"; p.write_text('{"voice_gender": "robot"}')
    assert Settings.load(p).voice_gender == "male"

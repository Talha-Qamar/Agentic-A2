from pharmacy_forecast.core import run


def test_run_empty(tmp_path):
    f = tmp_path / 'x.jsonl'
    f.write_text('')
    assert run(str(f))['n'] == 0

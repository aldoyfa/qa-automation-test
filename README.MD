# How to Run

Install dependencies:

```
pip install -r requirements.txt
python -m playwright install chromium
```

Run all tests:

```
python -m pytest test.py -v
```

Run test and generate HTML report:

```
$env:HEADLESS="1"
python -m pytest test.py -v --html=reports/report.html --self-contained-html
```

Run one test:

```
python -m pytest test.py::test_tc001 -v
```

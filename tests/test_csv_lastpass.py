import os

from utilities_perl.csv_lastpass import CSVLastPass


def test_read_testdata(data_dir):
    csv = CSVLastPass()
    rows = csv.read(os.path.join(data_dir, "testdata.csv"), {"sep_char": ","})
    assert rows == [
        {
            "url": "https://10.0.0.23",
            "username": "admin",
            "password": "admin",
            "totp": "",
            "extra": "",
            "name": "10.0.0.23",
            "grouping": "unittest",
            "fav": "0",
        },
        {
            "url": "https://www.paypal.com",
            "username": "mr42@example.com",
            "password": "hemmelig",
            "totp": "",
            "extra": "",
            "name": "paypal.com",
            "grouping": "unittest",
            "fav": "0",
        },
    ]


def test_read_lastpass(data_dir):
    csv = CSVLastPass()
    rows = csv.read(os.path.join(data_dir, "lastpass.csv"), {"sep_char": ","})
    assert len(rows) == 4

    assert rows[0]["extra"] == "Fluff text\nremember to keep a secret"
    assert rows[0]["name"] == "paypal.com"
    assert rows[0]["fav"] == "0"

    assert rows[1]["name"] == "Longtext"
    assert rows[1]["extra"] == (
        "Når passordet har løpt ut så bytt på password.com og ikke password.org\n"
        "\n"
        "I tilfelle DNS trøbbel\n"
        "example.com 8.8.8.8"
    )

    assert rows[2]["name"] == "circlekeurope.com"
    assert rows[2]["username"] == "user@example.com"
    assert rows[2]["password"] == "secret"
    assert rows[2]["url"].startswith("https://id.circlekeurope.com")

    assert rows[3]["name"] == "John Doe"
    assert rows[3]["extra"].startswith("NoteType:Address")
    assert rows[3]["extra"].rstrip().endswith("Fax:")

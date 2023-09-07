CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    transaction_type TEXT NOT NULL,
    user_id INTEGER,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    shares INTEGER,
    price FLOAT NOT NULL,
    total FLOAT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE portfolio (
    user_id INTEGER,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    shares INTEGER,
    price FLOAT NOT NULL,
    total FLOAT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
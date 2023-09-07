import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
db = SQL("sqlite:///finance.db")
'''uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)'''

# Get current time
now = datetime.now()
current_date = now.strftime("%m-%d-%Y")
current_time = now.strftime("%H:%M:%S")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    total = 0
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])

    for purchases in portfolio:
        stock_info = lookup(purchases["symbol"])
        if stock_info is not None:
            name = stock_info["name"]
            price = stock_info["price"]
            symbol = stock_info["symbol"]
            total_shares = price * int(purchases["shares"])
            total += total_shares
            db.execute("UPDATE portfolio SET price = ? WHERE user_id = ? AND symbol = ?",
                       price, session["user_id"], name)

            db.execute("UPDATE portfolio SET total = ? WHERE user_id = ? AND symbol = ?",
                       total_shares, session["user_id"], name)

    all_shares = total_value()
    return render_template("index.html", portfolio=portfolio, total=total, all_shares=all_shares)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        get_symbol = request.form.get("symbol")
        get_shares = request.form.get("shares")

        # Checks if user left fields empty
        if not get_symbol or not get_shares:
            flash("field empty", category="emptyfield")
            return apology("field empty", 400)

        # Checks if share amount is valid digit
        elif not get_shares.isdigit():
            flash("Invalid share amount", category="invalidshares")
            return apology("invalid amount", 400)

        bought_shares = int(get_shares)
        # Check if user inputs negative amount of shares
        if bought_shares <= 0:
            flash("Invalid share amount", category="invalidshares")
            return apology("invalid amount", 400)

        # If both fields are fulfilled
        # then look up symbol
        if get_symbol and get_shares:
            info = lookup(get_symbol)

            if info:
                name = info["name"]
                price = info["price"]
                symbol = info["symbol"]
                total = price * bought_shares

                # Obtain current amount of cash user has
                get_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                cash = get_cash[0]["cash"]

                # Checks if user has enough cash to buy shares
                if cash < total:
                    return apology("Not enough cash", 403)

                # Updates users cash after buying shares
                new_cash = cash - total
                session["cash"] = f"{new_cash:.2f}"
                db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

                # Add new row in transactions table
                db.execute("INSERT INTO transactions "
                           "(transaction_type, user_id, symbol, name, shares, price, total, date, time)\
                            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           "BUY",
                           session["user_id"],
                           symbol,
                           name,
                           bought_shares,
                           price,
                           total,
                           current_date,
                           current_time)

                # Get the current amount of shares the user has
                get_current_shares = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?",
                                                session["user_id"], name)
                if get_current_shares:
                    current_shares = get_current_shares[0]["shares"]
                else:
                    current_shares = 0
                new_shares = bought_shares + current_shares
                new_total = new_shares * price

                # Loop through portfolio to check if user already purchased
                # the symbol and updates it
                portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
                for purchase in portfolio:
                    if name == purchase["symbol"] and session["user_id"] == purchase["user_id"]:
                        db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                                   new_shares,
                                   session["user_id"],
                                   name)
                        db.execute("UPDATE portfolio SET total = ? WHERE user_id = ? AND symbol = ?",
                                   new_total,
                                   session["user_id"],
                                   name)
                        portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
                        flash("Purchase Successful!", category="purchased")
                        all_shares = total_value()
                        return render_template("index.html", portfolio=portfolio, total=total, all_shares=all_shares)

                # Else user has not purchased symbol before; insert new row
                db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, price, total)\
                            VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], name, name, bought_shares, price, new_total)

                flash("Purchase Successful!", category="purchased")
                all_shares = total_value()
                portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
                return render_template("index.html", portfolio=portfolio, total=total, all_shares=all_shares)

            # Checks if user input is a valid symbol
            else:
                flash("Symbol does not exist", category="invalid-symbol")
                return apology("invalid symbol", 400)

    # User reached route besides "POST"
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        remember_me = request.form.get("remember")
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["cash"] = "%.2f" % rows[0]["cash"]
        session["username"] = rows[0]["username"]

        if remember_me:
            app.config["SESSION_PERMANENT"] = True

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        get_symbol = request.form.get("symbol")

        if not get_symbol:
            flash("symbol field empty", category="symbol-empty")
            return apology("symbol field empty", 400)

        if get_symbol:
            info = lookup(get_symbol)
            if info:
                return render_template("quoted.html", info=info, current_date=current_date, current_time=current_time,)
            else:
                flash("Symbol does not exist", category="invalid-symbol")
                return apology("Symbol does not exist", 400)

    else:
        return render_template("quote.html", current_date=current_date, current_time=current_time)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        confirmpw = request.form.get("confirmation")

        # Ensure username was submitted
        if not name:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        elif password != confirmpw:
            return apology("Password does not match", 400)

        name_exist = db.execute("SELECT username FROM users WHERE username = ?", name)

        if name_exist:
            return apology("Name already taken", 400)

        hashed_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, hashed_pw)
        flash("Registration Successful!", category="message")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    stock_set = set()
    get_stocks = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])

    # Add symbols from user's portfolio into set
    for symbol in get_stocks:
        stock = symbol["symbol"]
        stock_set.add(stock)

    if request.method == "POST":
        get_symbol = request.form.get("symbol")
        get_shares = request.form.get("shares")

        # Get current amount of shares for symbol from user portfolio
        shares_amount = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?",
                                   session["user_id"], get_symbol)
        if not shares_amount:
            return apology("no stocks found", 400)

        user_shares = int(shares_amount[0]["shares"])

        if not get_symbol or not get_shares:
            flash("field empty", category="emptyfield")
            return apology("field empty", 400)

        elif not get_shares.isdigit():
            flash("Invalid share amount", category="invalidshares")
            return apology("invalid amount", 400)

        # Checks if symbol matches with any symbols in portfolio
        elif get_symbol not in stock_set:
            return apology("stock not owned", 400)

        sold_shares = int(get_shares)

        # Checks if user inputs negative amount of shares
        if sold_shares <= 0:
            flash("Invalid share amount", category="invalidshares")
            return apology("invalid amount", 400)

        # Checks if user try's to sell more shares than they have
        elif sold_shares > user_shares:
            return apology("not enough shares", 400)

        if get_symbol and get_shares:
            info = lookup(get_symbol)

            if info:
                name = info["name"]
                price = info["price"]
                symbol = info["symbol"]
                total = price * sold_shares

                get_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                cash = get_cash[0]["cash"]

                # Subtracts the amount of shares the user has
                # From the amount they want to sell
                shares_left = user_shares - sold_shares

                if shares_left == 0:
                    db.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], get_symbol)

                # Update new cash value after selling stock
                new_cash = cash + total
                cash_float = float(new_cash)

                db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_float, session["user_id"])
                db.execute("INSERT INTO transactions "
                           "(transaction_type, user_id, symbol, name, shares, price, total, date, time)\
                            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           "SELL",
                           session["user_id"],
                           symbol,
                           name,
                           sold_shares,
                           price,
                           total,
                           current_date,
                           current_time)

                flash("Sold!", category="sold")

                new_total = shares_left * price

                # Update values in portfolio
                db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                           shares_left, session["user_id"], name)

                db.execute("UPDATE portfolio SET total = ? WHERE user_id = ? AND symbol = ?",
                           new_total, session["user_id"], name)

                portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
                all_shares = total_value()
                return redirect("/")

            else:
                flash("Symbol does not exist", category="invalid-symbol")
                return apology("invalid symbol", 403)
    else:
        return render_template("sell.html", get_stocks=get_stocks)


def total_value():
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
    total = 0
    # Loop through total value for each symbol to sum them all up
    for purchase in portfolio:
        total += purchase["total"]

    cash_float = float(f"{float(session['cash']):.2f}")
    # print(cash_float)
    total += cash_float
    return total


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    current_password = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
    if request.method == "POST":
        password = request.form.get("password")
        newpw = request.form.get("newpw")
        confirm_newpw = request.form.get("confirm-newpw")

        if not password or not newpw:
            flash("Password Field Empty", category="password_empty")
            return render_template("changepw.html")

        same_pw = check_password_hash(current_password[0]["hash"], password)

        if same_pw:
            if newpw == confirm_newpw:
                hash_newpw = generate_password_hash(newpw)
                db.execute("UPDATE users SET hash = ? WHERE id = ?", hash_newpw, session["user_id"])
                flash("Password Succesfully Changed!", category="password_change")
                return render_template("login.html")

            flash("Password does not match", category="password_match")
            return render_template("changepw.html")

        else:
            flash("Password does not match", category="password_match")
            return render_template("changepw.html")

    else:
        return render_template("changepw.html")


if __name__ == "__main__":
    app.run(debug=True)
import os
import requests
from helper import login_required
from flask import Flask, session, redirect, render_template, request, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/search", methods=["GET"])
@login_required
def search():
    if not request.args.get("book"):
        return render_template("error.html", message="Must Provide Book to Search")
    query = "%" + request.args.get("book") +"%"
    #Capitalized input for Search
    query = query.title()
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn LIKE :query OR title LIKE :query OR author LIKE :query LIMIT 15", {"query": query})
    # Books not founded
    if rows.rowcount == 0:
        return render_template("error.html", message="No match")
    # Fetch all the results
    books = rows.fetchall()
    return render_template("results.html",books=books)

@app.route("/book/<isbn>", methods=["GET","POST"])
@login_required
def book(isbn):
    """ Update user review and reload page."""
    if request.method == "POST":
        # Check for existing review
        row1 = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn})

        # Save id into variable
        book = row1.fetchone() # (id,)
        book = book[0]

        rows = db.execute("SELECT rating, comment, time FROM reviews WHERE user_id=:user_id AND book_id=:book_id", {"user_id": session["user_id"], "book_id": book})
        if rows.rowcount == 1:
            flash("You've submitted a review in the past", "error")
            return redirect("/book/" + isbn)
        # Insert Review
        rating = int(request.form.get("rating"))
        comment = request.form.get("comment")
        db.execute("INSERT INTO reviews (user_id, book_id, comment, rating, time) VALUES (:user_id, :book_id, :comment, :rating, CURRENT_TIMESTAMP)", {"user_id": session["user_id"], "book_id": book, "comment":comment ,"rating":rating})
        db.commit()
        flash("Review subbmited", "success")
        return redirect("/book/" + isbn)
    else:
        rows = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn=:isbn", {"isbn": isbn})
        if rows.rowcount == 0:
            return render_template("error.html", message="Book Does Not Exists")
        bookData=rows.fetchone()
        bookData=list(bookData)

        ''' Connect to GoodReads API'''
        key = os.getenv("GOODREADS_KEY")
        query = requests.get("https://www.goodreads.com/book/review_counts.json",params={"key": key, "isbns": isbn})

        response = query.json()
        response = response['books'][0]
        bookData.append(response)
        print(bookData)

        row = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn})

        # Save id into variable
        book = row.fetchone() # (id,)
        book = book[0]

        # Fetch book reviews
        # Date formatting (https://www.postgresql.org/docs/9.1/functions-formatting.html)
        results = db.execute("SELECT users.name, comment, rating, to_char(time, 'DD Mon YY - HH24:MI:SS') as time FROM users INNER JOIN reviews ON users.id = reviews.user_id WHERE book_id = :book ORDER BY time",{"book": book})

        reviews = results.fetchall()
        print(reviews)
        return render_template("book.html", bookData=bookData, reviews=reviews)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Forget any user_id
        session.clear()

        # Ensure name was submitted
        if not request.form.get("name"):
            return render_template("error.html", message="Must Provide Name")

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", message="Must Provide Username")

        # Ensure password was submitted
        if not request.form.get("password"):
            return render_template("error.html", message="Must Provide Password")

        if request.form.get("password") != request.form.get("confirmation"):
            return render_template("error.html", message="Password Do Not Match")

        # Query database for username & insert user if no existing clash
        checkUser = db.execute("SELECT * FROM users WHERE username = :username",{"username":request.form.get("username")}).fetchone()

        if checkUser:
            return render_template("error.html", message="Username Existed")

        hashPassword = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, password, name) VALUES (:username, :password, :name)",{"username":request.form.get("username"),"password":hashPassword,"name":request.form.get("name")})
        db.commit()

        # Redirect user to home page
        return render_template("login.html")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username=request.form.get("username")
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", message="Must Provide Username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("error.html", message="Must Provide Password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
        print(rows)
        # Ensure username exists and password is correct
        if rows == None or not check_password_hash(rows[3], request.form.get("password")):
            return render_template("error.html", message="invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]
        session["user_username"] = rows[1]
        session["user_name"] = rows[2]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """ Log user out """
    session.clear()
    return redirect("/")

@app.route("/api/<isbn>", methods=['GET'])
@login_required
def api_book(isbn):

    row = db.execute("SELECT title, author, year, isbn, COUNT(reviews.id) as review_count, AVG(reviews.rating) as average_score FROM books INNER JOIN reviews ON books.id = reviews.book_id WHERE isbn = :isbn GROUP BY title, author, year, isbn", {"isbn": isbn})

    # Check if review exists
    if row.rowcount != 1:
        return jsonify({"Error": "No review exist"}), 404

    # Fetch results
    tmp = row.fetchone()

    result = dict(tmp.items())

    result['average_score'] = float('%.1f'%(result['average_score']))

    return jsonify(result)

# Project 1

Web Programming with Python and JavaScript

**Heroku Weblink**


**Environment variable**
FLASK_APP=application.py
DATABASE_URL=Postgresql DB URL
GOODREADS_KEY=Goodreads API Key from www.goodreads.com

**Basic Functionality**
Register,Login,logout

Search books via bookname, author or ISBN

Review books

**Access to API**
URL: /api/<isbn>
Require Login prior to API access
If review & isbn exists, return json object as follow:
```
{
  "author": "Carl Sagan",
  "average_score": 5.0,
  "isbn": "2266079999",
  "review_count": 1,
  "title": "Contact",
  "year": "1985"
}
```

If review or isbn does not exists, return error with code 404.

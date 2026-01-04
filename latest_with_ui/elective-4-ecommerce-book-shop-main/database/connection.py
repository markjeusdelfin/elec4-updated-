import mysql.connector


def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='', 
        database='book_ecommerce',
        autocommit=True
    )
    return conn

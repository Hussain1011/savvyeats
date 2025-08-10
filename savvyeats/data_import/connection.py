import pymysql
import frappe

def run_external_mysql_query(query, params=None):
    connection = pymysql.connect(
        host="34.18.13.147",
        user="savvy_eats_dfhdjgjhdhj",
        password="kaejrsdjkhfaAsjXk56h4_yjghwrjkrgth",
        database="savvy_eats",
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        connection.close()

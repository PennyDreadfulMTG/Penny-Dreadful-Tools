import sqlite3
import time

def price_info(card):
    conn = sqlite3.connect('prices.db')
    sql = 'SELECT CAST(MIN(p.price) AS FLOAT) / 100.0 AS price FROM price AS p INNER JOIN (SELECT name, MAX(`time`) AS `time` FROM price GROUP BY name, `set`, premium) AS p2 ON p.name = p2.name AND p.`time` = p2.`time` WHERE p.name = ?'
    price = conn.cursor().execute(sql, [card.name]).fetchone()[0]

    sql = """SELECT CAST(SUM(CASE WHEN price = 1 THEN 1 ELSE 0 END) AS FLOAT) / CAST(COUNT(*) AS FLOAT) AS legal
    FROM (
        SELECT name, `time`, MIN(price) AS price
        FROM price
        WHERE time >= ?
        GROUP BY name, `time`
    )
    WHERE name = ?"""

    now = time.time()
    week = now - 60 * 60 * 24 * 7
    month = now - 60 * 60 * 24 * 7 * 30

    week = conn.cursor().execute(sql, [week, card.name]).fetchone()[0]
    month = conn.cursor().execute(sql, [month, card.name]).fetchone()[0]

    return {
        'price': price,
        'week': week,
        'month': month,
    }

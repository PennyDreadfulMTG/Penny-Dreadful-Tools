import sqlite3
import time

import rotation

def info(card):
    info = {}

    conn = sqlite3.connect('prices.db')
    last_rotation = rotation.last_rotation().timestamp()

    sql = 'SELECT CAST(MIN(price) AS FLOAT) / 100.0 FROM price WHERE `time` > ? AND name = ? GROUP BY `time`'
    rs = conn.cursor().execute(sql, [last_rotation, card.name]).fetchall()
    info['low'] = min(p[0] for p in rs)
    info['high'] = max(p[0] for p in rs)

    sql = 'SELECT CAST(MIN(p.price) AS FLOAT) / 100.0 AS price FROM price AS p INNER JOIN (SELECT name, MAX(`time`) AS `time` FROM price GROUP BY name, `set`, premium) AS p2 ON p.name = p2.name AND p.`time` = p2.`time` WHERE p.name = ?'
    info['price'] = conn.cursor().execute(sql, [card.name]).fetchone()[0]

    sql = """SELECT CAST(SUM(CASE WHEN price = 1 THEN 1 ELSE 0 END) AS FLOAT) / CAST(COUNT(*) AS FLOAT) AS legal
    FROM (
        SELECT name, `time`, MIN(price) AS price
        FROM price
        WHERE `time` >= ?
        GROUP BY name, `time`
    )
    WHERE name = ?"""

    now = time.time()
    week = now - 60 * 60 * 24 * 7
    month = now - 60 * 60 * 24 * 7 * 30

    info['week'] = conn.cursor().execute(sql, [week, card.name]).fetchone()[0]
    info['month'] = conn.cursor().execute(sql, [month, card.name]).fetchone()[0]
    info['rotation'] = conn.cursor().execute(sql, [last_rotation, card.name]).fetchone()[0]

    return info

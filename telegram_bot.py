import sys
import subprocess

from influxdb import InfluxDBClient
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from pymongo import MongoClient

from telegram_config import TOKEN, DB1, DB2, USER, PASS


SERVICES = ["cube",
            "grafana-server",
            "influxdb",
            "lircd",
            "mosquitto",
            "pep",
            "telegraf",
            "telegram-bot",
            "temp",
            "unifi",
            "zigbee2mqtt"]

CMDS = {"pomiar": "pomiar",
        "meteo": "meteo",
        "system": "system",
        "services": "services",
        "wifi": "wifi"}

client1 = InfluxDBClient('localhost', 8086, USER, PASS, DB1)
client2 = InfluxDBClient('localhost', 8086, USER, PASS, DB2)

mongo = MongoClient("mongodb://localhost:27117/")
mongo_db1 = mongo["ace"]
mongo_db2 = mongo["ace_stat"]
client3 = mongo_db1["user"]
client4 = mongo_db2["stat_5minutes"]


def wifi_users():
    query_users = client3.find()
    query_clients = client4.find({}, {"x-set-user-num_sta": 1}).sort('_id', 1).limit(1)

    users = {}
    for u in query_users:
        if 'name' in u:
            users[str(u['mac'])] = u['name']
        elif 'hostname' in u:
            users[str(u['mac'])] = u['hostname']

    names = []
    for c in query_clients[0]["x-set-user-num_sta"]:
        for m, u in users.items():
            if m == c:
                names.append(u)

    t = ""
    for n in sorted(names):
        t = t + n + "\n"

    return t


def is_active(service):
    """
    check if linux service works
    :param service: service name
    :return: true or false
    """
    cmd = '/bin/systemctl status ' + service
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    lines = str(proc.communicate()[0]).split('\n')

    for line in lines:
        if 'Active:' in line:
            if '(running)' in line:
                return True

    return False


def meteo():
    """
    read the latest weather information from InfluxDB
    :return: answer string
    """
    d = []

    for m in ("temp_wew", "a_temp", "temp_zewn", "a_wilg", "a_cisn"):
        q = client1.query("select * from " + m + " group by * order by desc limit 1", database=DB1)
        d.append(str(round(list(q.get_points())[0]['value'], 1)))

    r = '<b><code>' + d[0] + 'C</code></b>, <b><code>' + d[1] + 'C</code></b> - temperatura wewnątrz\n' + \
        '<b><code>' + d[2] + 'C</code></b> - temperatura na zewnątrz\n' + \
        '<b><code>' + d[3] + '%</code></b> - wilgotność\n' + \
        '<b><code>' + d[4] + 'hPa</code></b> - ciśnienie\n'

    return r


def system():
    """
    read the latest system parameters from InfluxDB
    :return: answer string
    """
    d = []

    q = client2.query("SELECT value / 1000 FROM cpu_temperature group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['value'], 1)))

    q = client2.query("SELECT usage_idle * -1 + 100 FROM cpu WHERE cpu='cpu-total' group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['usage_idle'], 1)))

    q = client2.query("SELECT used_percent FROM mem group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['used_percent'], 1)))

    q = client2.query("SELECT used_percent FROM disk group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['used_percent'], 1)))

    r = '<b><code>' + d[0] + 'C</code></b> - temperatura CPU\n' + \
        '<b><code>' + d[1] + '%</code></b> - użycie CPU\n' + \
        '<b><code>' + d[2] + '%</code></b> - użycie RAM\n' + \
        '<b><code>' + d[3] + '%</code></b> - zajętość dysku /\n'

    return r


def start(update, context):
    """
    send a message when the user is connected for the first time
    :param update: incoming telegram update
    :param context: the context object
    """
    update.message.reply_text('Tu Artur Klimek Bot')


def help(update, context):
    """
    send a message when the /help command is sent
    :param update: incoming telegram update
    :param context: the context object
    """
    t = 'Dostępne polecenia:'
    for c in CMDS:
        t = t + '\n"' + c + '"'

    update.message.reply_text(t)


def msg(update, context):
    """
    Handling of sent user messages
    :param update: incoming telegram update
    :param context: the context object
    """
    if update.message.text.lower() == CMDS['meteo']:
        update.message.reply_text(meteo(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['system']:
        update.message.reply_text(system(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['pomiar']:
        update.message.reply_text("<b><u>System:</u></b>\n" + system(), parse_mode=ParseMode.HTML)
        update.message.reply_text("<b><u>Meteo:</u></b>\n" + meteo(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['services']:
        t = ''
        for s in SERVICES:
            t = t + s + ' is' + (' running' if is_active(s) else ' <u><b>STOPPED</b></u>') + '\n'
        update.message.reply_text(t, parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['wifi']:
        update.message.reply_text(wifi_users(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == 'cześć':
        update.message.reply_text('Cześć!')


def main():
    """
    Run bot.
    """
    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    dp.add_handler(MessageHandler(Filters.text, msg))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()


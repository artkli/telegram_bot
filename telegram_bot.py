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
mongo_db = mongo["ace"]
client3 = mongo_db["user"]
client4 = mongo_db["event"]


def wifi_users():
    """
    read the WiFi devices connected
    :return: answer string
    """
    query_users = client3.find()
    query_events = client4.find()

    users = {}
    for u in query_users:
        if 'name' in u:
            users[str(u['mac'])] = u['name']
        elif 'hostname' in u:
            users[str(u['mac'])] = u['hostname']

    events = []
    for e in query_events:
        if 'user' in e:
            if 'key' in e:
                if e['key'] == 'EVT_WU_Connected':
                    a = [e['time'], e['key'], e['user'], e['ssid'], e['channel']]
                    events.append(a)
                    if e['user'] not in users:
                        users[str(e['user'])] = '[' + e['user'].replace(':','').upper() + ']'
                if e['key'] == 'EVT_WU_Disconnected':
                    a = [e['time'], e['key'], e['user']]
                    events.append(a)
                    if e['user'] not in users:
                        users[str(e['user'])] = '[' + e['user'].replace(':','').upper() + ']'

    sorted_events = sorted(events, key=lambda x: x[0])

    last_events = []
    for m, h in users.items():
        r = []
        for i in sorted_events:
            if i[2] == m:
                r = i
                r.append(h)
        last_events.append(r)

    r = ""
    i = 1
    for e in last_events:
        print(e)
        if e and e[1] == 'EVT_WU_Connected':
            c = ' (5GHz)' if int(e[4]) > 16 else ' (2.4GHz)'
            r = r + str(i) + '. <b><code>' + e[5] + '</code></b> - ' + e[3] + c + '\n'
            i = i + 1

    return r


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

def services():
    """
    read status of services
    :return: answer string
    """
    t = ''
    for s in SERVICES:
        t = t + '<b><code>' + s + '</code></b> is' + (' running' if is_active(s) else ' <u><b>STOPPED</b></u>') + '\n'

    return t


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

    q = client2.query("SELECT load5 FROM system group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['load5'], 1)))

    q = client2.query("SELECT used_percent FROM mem group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['used_percent'], 1)))

    q = client2.query("SELECT used_percent FROM disk group by * order by desc limit 1",
                      database=DB2)
    d.append(str(round(list(q.get_points())[0]['used_percent'], 1)))

    r = '<b><code>' + d[0] + 'C</code></b> - temperatura CPU\n' + \
        '<b><code>' + d[1] + '%</code></b> - użycie CPU\n' + \
        '<b><code>' + d[2] + '</code></b> - kolejka procesów\n' + \
        '<b><code>' + d[3] + '%</code></b> - użycie RAM\n' + \
        '<b><code>' + d[4] + '%</code></b> - zajętość dysku /\n'

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

    if update.message.text.lower() == CMDS['services']:
        update.message.reply_text(services(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['wifi']:
        update.message.reply_text(wifi_users(), parse_mode=ParseMode.HTML)

    if update.message.text.lower() == CMDS['pomiar']:
        update.message.reply_text("<b><u>Meteo:</u></b>\n" + meteo(), parse_mode=ParseMode.HTML)
        update.message.reply_text("<b><u>System:</u></b>\n" + system(), parse_mode=ParseMode.HTML)
        update.message.reply_text("<b><u>Services:</u></b>\n" + services(), parse_mode=ParseMode.HTML)
        update.message.reply_text("<b><u>Wifi:</u></b>\n" + wifi_users(), parse_mode=ParseMode.HTML)

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



#!/usr/bin/python3
import aiohttp
import asyncio
import argparse
import base64
import datetime
import json
import logging
import random
import smtplib
import string as s
import sys
import threading
import re
from time import sleep
from typing import Dict, List

import dns.resolver

from requests_html import AsyncHTMLSession  # type: ignore
from aiohttp_socks import ProxyConnector


# TODO: move to main function
uaLst = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.106 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36"
]

logging.basicConfig(format='%(message)s')
logger = logging.getLogger('mailcat')
logger.setLevel(100)

def randstr(num):
    return ''.join(random.sample((s.ascii_lowercase + s.ascii_uppercase + s.digits), num))


def sleeper(sList, s_min, s_max):
    for ind in sList:
        if sList.index(ind) < (len(sList) - 1):
            sleep(random.uniform(s_min, s_max))


def via_tor():
    connector = ProxyConnector.from_url('socks5://127.0.0.1:9050')
    session = aiohttp.ClientSession(connector=connector)
    return session


def simple_session():
    return aiohttp.ClientSession()


def code250(mailProvider, target):
    target = target
    providerLst = []

    randPref = ''.join(random.sample(s.ascii_lowercase, 6))
    fromAddress = "{}@{}".format(randPref, mailProvider)
    targetMail = "{}@{}".format(target, mailProvider)

    records = dns.resolver.Resolver().resolve(mailProvider, 'MX')
    mxRecord = records[0].exchange
    mxRecord = str(mxRecord)

    try:
        server = smtplib.SMTP()
        server.set_debuglevel(0)

        server.connect(mxRecord)
        server.helo(server.local_hostname)
        server.mail(fromAddress)
        code, message = server.rcpt(targetMail)

        if code == 250:
            providerLst.append(targetMail)
            return providerLst

    except Exception as e:
        logger.error(e, exc_info=True)

    return []


async def gmail(target, req_session_fun) -> Dict:
    result = {}
    gmailChkLst = code250("gmail.com", target)
    if gmailChkLst:
        result["Google"] = gmailChkLst[0]

    await asyncio.sleep(0)
    return result


async def yandex(target, req_session_fun) -> Dict:
    result = {}
    yaAliasesLst = ["yandex.by",
                    "yandex.kz",
                    "yandex.ua",
                    "yandex.com",
                    "ya.ru"]
    yaChkLst = code250("yandex.ru", target)
    if yaChkLst:
        yaAliasesLst = ['{}@{}'.format(target, yaAlias) for yaAlias in yaAliasesLst]
        yaMails = list(set(yaChkLst + yaAliasesLst))
        result["Yandex"] = yaMails

    await asyncio.sleep(0)
    return result


async def proton(target, req_session_fun) -> Dict:
    result = {}
    
    protonLst = ["protonmail.com", "protonmail.ch", "pm.me"]
    protonSucc = []
    sreq = req_session_fun()

    protonURL = "https://mail.protonmail.com/api/users/available?Name={}".format(target)

    headers = { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0",
                "Accept": "application/vnd.protonmail.v1+json",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Referer": "https://mail.protonmail.com/create/new?language=en",
                "x-pm-appversion": "Web_3.16.19",
                "x-pm-apiversion": "3",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "DNT": "1", "Connection": "close"}

    try:

        chkProton = await sreq.get(protonURL, headers=headers, timeout=3)

        async with chkProton:
            if chkProton.status == 409:
                resp = await chkProton.json()
                exists = resp['Error']
                if exists == "Username already used":
                    protonSucc = ["{}@{}".format(target, protodomain) for protodomain in protonLst]

    except Exception as e:
        logger.error(e, exc_info=True)
    
    if protonSucc:
        result["Proton"] = protonSucc

    await sreq.close()

    return result


async def mailRu(target, req_session_fun) -> Dict:
    result = {}

    # headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:68.0) Gecko/20100101 Firefox/68.0', 'Referer': 'https://account.mail.ru/signup?from=main&rf=auth.mail.ru'}
    mailRU = ["mail.ru", "bk.ru", "inbox.ru", "list.ru", "internet.ru"]
    mailRuSucc = []
    sreq = req_session_fun()

    for maildomain in mailRU:
        try:
            headers = {'User-Agent': random.choice(uaLst)}
            mailruMail = "{}@{}".format(target, maildomain)
            data = {'email': mailruMail}

            chkMailRU = await sreq.post('https://account.mail.ru/api/v1/user/exists', headers=headers, data=data, timeout=5)

            async with chkMailRU:
                if chkMailRU.status == 200:
                    resp = await chkMailRU.json()
                    exists = resp['body']['exists']
                    if exists:
                        mailRuSucc.append(mailruMail)

        except Exception as e:
            logger.error(e, exc_info=True)

        sleep(random.uniform(0.5, 2))

    if mailRuSucc:
        result["MailRU"] = mailRuSucc

    await sreq.close()

    return result


async def rambler(target, req_session_fun) -> Dict:  # basn risk
    result = {}

    ramblerMail = ["rambler.ru", "lenta.ru", "autorambler.ru", "myrambler.ru", "ro.ru", "rambler.ua"]
    ramblerSucc = []
    sreq = req_session_fun()

    for maildomain in ramblerMail:

        try:
            targetMail = "{}@{}".format(target, maildomain)

            # reqID = ''.join(random.sample((s.ascii_lowercase + s.ascii_uppercase + s.digits), 20))
            reqID = randstr(20)
            userAgent = random.choice(uaLst)
            ramblerChkURL = "https://id.rambler.ru:443/jsonrpc"

            #            "Referer": "https://id.rambler.ru/login-20/mail-registration?back=https%3A%2F%2Fmail.rambler.ru%2F&rname=mail&param=embed&iframeOrigin=https%3A%2F%2Fmail.rambler.ru",

            headers = {"User-Agent": userAgent,
                       "Referer": "https://id.rambler.ru/login-20/mail-registration?utm_source=head"
                                  "&utm_campaign=self_promo&utm_medium=header&utm_content=mail&rname=mail"
                                  "&back=https%3A%2F%2Fmail.rambler.ru%2F%3Futm_source%3Dhead%26utm_campaign%3Dself_promo%26utm_medium%3Dheader%26utm_content%3Dmail"
                                  "&param=embed&iframeOrigin=https%3A%2F%2Fmail.rambler.ru&theme=mail-web",
                       "Content-Type": "application/json",
                       "Origin": "https://id.rambler.ru",
                       "X-Client-Request-Id": reqID}

            ramblerJSON = {"method": "Rambler::Id::login_available", "params": [{"login": targetMail}], "rpc": "2.0"}
            ramblerChk = await sreq.post(ramblerChkURL, headers=headers, json=ramblerJSON, timeout=5)

            async with ramblerChk:
                if ramblerChk.status == 200:
                    try:
                        resp = await ramblerChk.json(content_type=None)
                        exist = resp['result']['profile']['status']
                        if exist == "exist":
                            ramblerSucc.append(targetMail)
                            # print("[+] Success with {}".format(targetMail))
                        # else:
                        #    print("[-]".format(ramblerChk.text))
                    except KeyError as e:
                        logger.error(e, exc_info=True)

            sleep(random.uniform(4, 6))  # don't reduce

        except Exception as e:
            logger.error(e, exc_info=True)

    if ramblerSucc:
        result["Rambler"] = ramblerSucc

    await sreq.close()

    return result


async def tuta(target, req_session_fun) -> Dict:
    result = {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'}

    tutaMail = ["tutanota.com", "tutanota.de", "tutamail.com", "tuta.io", "keemail.me"]
    tutaSucc = []
    sreq = req_session_fun()

    for maildomain in tutaMail:

        try:

            targetMail = "{}@{}".format(target, maildomain)
            tutaURL = "https://mail.tutanota.com/rest/sys/mailaddressavailabilityservice?_body="

            tutaCheck = await sreq.get(
                '{}%7B%22_format%22%3A%220%22%2C%22mailAddress%22%3A%22{}%40{}%22%7D'.format(tutaURL, target,
                                                                                             maildomain),
                headers=headers, timeout=5)

            async with tutaCheck:
                if tutaCheck.status == 200:
                    resp = await tutaCheck.json()
                    exists = resp['available']

                    if exists == "0":
                        tutaSucc.append(targetMail)

            sleep(random.uniform(2, 4))

        except Exception as e:
            logger.error(e, exc_info=True)

    if tutaSucc:
        result["Tutanota"] = tutaSucc

    await sreq.close()

    return result


async def yahoo(target, req_session_fun) -> Dict:
    result = {}

    yahooURL = "https://login.yahoo.com:443/account/module/create?validateField=yid"
    yahooCookies = {"B": "10kh9jteu3edn&b=3&s=66", "AS": "v=1&s=wy5fFM96"}  # 13 8
    # yahooCookies = {"B": "{}&b=3&s=66".format(randstr(13)), "AS": "v=1&s={}".format(randstr(8))} # 13 8
    headers = {"User-Agent": random.choice(uaLst),
               "Accept": "*/*", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate",
               "Referer": "https://login.yahoo.com/account/create?.src=ym&.lang=en-US&.intl=us&.done=https%3A%2F%2Fmail.yahoo.com%2Fd&authMechanism=primary&specId=yidReg",
               "content-type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
               "DNT": "1", "Connection": "close"}

    # yahooPOST = {"specId": "yidReg", "crumb": randstr(11), "acrumb": randstr(8), "yid": target} # crumb: 11, acrumb: 8
    yahooPOST = {"specId": "yidReg", "crumb": "bshN8x9qmfJ", "acrumb": "wy5fFM96", "yid": target}
    sreq = req_session_fun()

    try:
        yahooChk = await sreq.post(yahooURL, headers=headers, cookies=yahooCookies, data=yahooPOST, timeout=5)

        body = await yahooChk.text()
        if '"IDENTIFIER_EXISTS"' in body:
            result["Yahoo"] = "{}@yahoo.com".format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def outlook(target, req_session_fun) -> Dict:
    result = {}
    liveSucc = []
    sreq = AsyncHTMLSession(loop=asyncio.get_event_loop())
    headers = {"User-Agent": random.choice(uaLst)}
    liveLst = ["outlook.com", "hotmail.com"]
    url_template = 'https://signup.live.com/?username={}@{}&uaid=f746d3527c20414d8c86fd7f96613d85&lic=1'

    for maildomain in liveLst:
        try:
            liveChk = await sreq.get(url_template.format(target, maildomain), headers=headers)
            await liveChk.html.arender(sleep=10)

            if "suggLink" in liveChk.html.html:
                liveSucc.append("{}@{}".format(target, maildomain))

        except Exception as e:
            logger.error(e, exc_info=True)

    if liveSucc:
        result["Live"] = liveSucc

    await sreq.close()

    return result


async def zoho(target, req_session_fun) -> Dict:
    result = {}

    headers = {
        "User-Agent": "User-Agent: Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.7113.93 Safari/537.36",
        "Referer": "https://www.zoho.com/",
        "Origin": "https://www.zoho.com"
    }

    zohoURL = "https://accounts.zoho.com:443/accounts/validate/register.ac"
    zohoPOST = {"username": target, "servicename": "VirtualOffice", "serviceurl": "/"}
    sreq = req_session_fun()

    try:
        zohoChk = await sreq.post(zohoURL, headers=headers, data=zohoPOST, timeout=10)

        async with zohoChk:
            if zohoChk.status == 200:
                # if "IAM.ERROR.USERNAME.NOT.AVAILABLE" in zohoChk.text:
                #    print("[+] Success with {}@zohomail.com".format(target))
                resp = await zohoChk.json()
                if resp['error']['username'] == 'This username is taken':
                    result["Zoho"] = "{}@zohomail.com".format(target)
                    # print("[+] Success with {}@zohomail.com".format(target))
    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def lycos(target, req_session_fun) -> Dict:
    result = {}

    lycosURL = "https://registration.lycos.com/usernameassistant.php?validate=1&m_AID=0&t=1625674151843&m_U={}&m_PR=27&m_SESSIONKEY=4kCL5VaODOZ5M5lBF2lgVONl7tveoX8RKmedGRU3XjV3xRX5MqCP2NWHKynX4YL4".format(
        target)

    headers = {
        "User-Agent": "User-Agent: Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.7113.93 Safari/537.36",
        "Referer": "https://registration.lycos.com/register.php?m_PR=27&m_E=7za1N6E_h_nNSmIgtfuaBdmGpbS66MYX7lMDD-k9qlZCyq53gFjU_N12yVxL01F0R_mmNdhfpwSN6Kq6bNfiqQAA",
        "X-Requested-With": "XMLHttpRequest"}
    sreq = req_session_fun()

    try:
        lycosChk = await sreq.get(lycosURL, headers=headers, timeout=10)

        async with lycosChk:
            if lycosChk.status == 200:
                resp = await lycosChk.text()
                if resp == "Unavailable":
                    result["Lycos"] = "{}@lycos.com".format(target)
    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def eclipso(target, req_session_fun) -> Dict:  # high ban risk + false positives after
    result = {}

    eclipsoSucc = []

    eclipsoLst = ["eclipso.eu",
                  "eclipso.de",
                  "eclipso.at",
                  "eclipso.ch",
                  "eclipso.be",
                  "eclipso.es",
                  "eclipso.it",
                  "eclipso.me",
                  "eclipso.nl",
                  "eclipso.email"]

    headers = {'User-Agent': random.choice(uaLst),
               'Referer': 'https://www.eclipso.eu/signup/tariff-5',
               'X-Requested-With': 'XMLHttpRequest'}
    sreq = req_session_fun()

    for maildomain in eclipsoLst:
        try:
            targetMail = "{}@{}".format(target, maildomain)

            eclipsoURL = "https://www.eclipso.eu/index.php?action=checkAddressAvailability&address={}".format(
                targetMail)
            chkEclipso = await sreq.get(eclipsoURL, headers=headers, timeout=5)

            async with chkEclipso:
                if chkEclipso.status == 200:
                    resp = await chkEclipso.text()
                    if '>0<' in resp:
                        eclipsoSucc.append(targetMail)
        except Exception as e:
            logger.error(e, exc_info=True)

        sleep(random.uniform(2, 4))

    if eclipsoSucc:
        result["Eclipso"] = eclipsoSucc

    await sreq.close()

    return result


async def posteo(target, req_session_fun) -> Dict:
    result = {}

    posteoLst = [
        "posteo.af",
        "posteo.at",
        "posteo.be",
        "posteo.ca",
        "posteo.ch",
        "posteo.cl",
        "posteo.co",
        "posteo.co.uk",
        "posteo.com.br",
        "posteo.cr",
        "posteo.cz",
        "posteo.de",
        "posteo.dk",
        "posteo.ee",
        "posteo.es",
        "posteo.eu",
        "posteo.fi",
        "posteo.gl",
        "posteo.gr",
        "posteo.hn",
        "posteo.hr",
        "posteo.hu",
        "posteo.ie",
        "posteo.in",
        "posteo.is",
        "posteo.it",
        "posteo.jp",
        "posteo.la",
        "posteo.li",
        "posteo.lt",
        "posteo.lu",
        "posteo.me",
        "posteo.mx",
        "posteo.my",
        "posteo.net",
        "posteo.nl",
        "posteo.no",
        "posteo.nz",
        "posteo.org",
        "posteo.pe",
        "posteo.pl",
        "posteo.pm",
        "posteo.pt",
        "posteo.ro",
        "posteo.ru",
        "posteo.se",
        "posteo.sg",
        "posteo.si",
        "posteo.tn",
        "posteo.uk",
        "posteo.us"]

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36',
        'Referer': 'https://posteo.de/en/signup',
        'X-Requested-With': 'XMLHttpRequest'}

    sreq = req_session_fun()
    try:
        posteoURL = "https://posteo.de/users/new/check_username?user%5Busername%5D={}".format(target)
        chkPosteo = await sreq.get(posteoURL, headers=headers, timeout=5)

        async with chkPosteo:
            if chkPosteo.status == 200:
                resp = await chkPosteo.text()
                if resp == "false":
                    result["Posteo"] = ["{}@posteo.net".format(target),
                                        "~50 aliases: https://posteo.de/en/help/which-domains-are-available-to-use-as-a-posteo-alias-address"]
    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def mailbox(target, req_session_fun) -> Dict:  # tor RU
    result = {}

    mailboxURL = "https://register.mailbox.org:443/ajax"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36"}
    mailboxJSON = {"account_name": target, "action": "validateAccountName"}

    existiert = "Der Accountname existiert bereits."
    sreq = req_session_fun()

    try:
        chkMailbox = await sreq.post(mailboxURL, headers=headers, json=mailboxJSON, timeout=10)

        async with chkMailbox:
            resp = await chkMailbox.text()
            if resp == existiert:
                result["MailBox"] = "{}@mailbox.org".format(target)
    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def firemail(target, req_session_fun) -> Dict:  # tor RU
    result = {}

    firemailSucc = []

    firemailDomains = ["firemail.at", "firemail.de", "firemail.eu"]

    headers = {'User-Agent': random.choice(uaLst),
               'Referer': 'https://firemail.de/E-Mail-Adresse-anmelden',
               'X-Requested-With': 'XMLHttpRequest'}
    sreq = req_session_fun()

    for firemailDomain in firemailDomains:
        try:
            targetMail = "{}@{}".format(target, firemailDomain)

            firemailURL = "https://firemail.de/index.php?action=checkAddressAvailability&address={}".format(targetMail)
            chkFiremail = await sreq.get(firemailURL, headers=headers, timeout=10)

            async with chkFiremail:
                if chkFiremail.status == 200:
                    resp = await chkFiremail.text()
                    if '>0<' in resp:
                        firemailSucc.append("{}".format(targetMail))
        except Exception as e:
            logger.error(e, exc_info=True)

        sleep(random.uniform(2, 4))

    if firemailSucc:
        result["Firemail"] = firemailSucc

    await sreq.close()

    return result


async def fastmail(target, req_session_fun) -> Dict:  # sanctions against Russia) TOR + 4 min for check in loop(
    result = {}

    # Registration form on fastmail website automatically lowercase all input.
    # If uppercase letters are used false positive results are returned.
    target = target.lower()

    # validate target syntax to prevent false positive results
    match = re.search(r'^\w{3,40}$', target)

    if not match:
        return result

    fastmailSucc = []

    fastmailLst = [
        "fastmail.com", "fastmail.cn", "fastmail.co.uk", "fastmail.com.au",
        "fastmail.de", "fastmail.es", "fastmail.fm", "fastmail.fr",
        "fastmail.im", "fastmail.in", "fastmail.jp", "fastmail.mx",
        "fastmail.net", "fastmail.nl", "fastmail.org", "fastmail.se",
        "fastmail.to", "fastmail.tw", "fastmail.uk", "fastmail.us",
        "123mail.org", "airpost.net", "eml.cc", "fmail.co.uk",
        "fmgirl.com", "fmguy.com", "mailbolt.com", "mailcan.com",
        "mailhaven.com", "mailmight.com", "ml1.net", "mm.st",
        "myfastmail.com", "proinbox.com", "promessage.com", "rushpost.com",
        "sent.as", "sent.at", "sent.com", "speedymail.org",
        "warpmail.net", "xsmail.com", "150mail.com", "150ml.com",
        "16mail.com", "2-mail.com", "4email.net", "50mail.com",
        "allmail.net", "bestmail.us", "cluemail.com", "elitemail.org",
        "emailcorner.net", "emailengine.net", "emailengine.org", "emailgroups.net",
        "emailplus.org", "emailuser.net", "f-m.fm", "fast-email.com",
        "fast-mail.org", "fastem.com", "fastemail.us", "fastemailer.com",
        "fastest.cc", "fastimap.com", "fastmailbox.net", "fastmessaging.com",
        "fea.st", "fmailbox.com", "ftml.net", "h-mail.us",
        "hailmail.net", "imap-mail.com", "imap.cc", "imapmail.org",
        "inoutbox.com", "internet-e-mail.com", "internet-mail.org",
        "internetemails.net", "internetmailing.net", "jetemail.net",
        "justemail.net", "letterboxes.org", "mail-central.com", "mail-page.com",
        "mailandftp.com", "mailas.com", "mailc.net", "mailforce.net",
        "mailftp.com", "mailingaddress.org", "mailite.com", "mailnew.com",
        "mailsent.net", "mailservice.ms", "mailup.net", "mailworks.org",
        "mymacmail.com", "nospammail.net", "ownmail.net", "petml.com",
        "postinbox.com", "postpro.net", "realemail.net", "reallyfast.biz",
        "reallyfast.info", "speedpost.net", "ssl-mail.com", "swift-mail.com",
        "the-fastest.net", "the-quickest.com", "theinternetemail.com",
        "veryfast.biz", "veryspeedy.net", "yepmail.net", "your-mail.com"]

    headers = {"User-Agent": random.choice(uaLst),
               "Referer": "https://www.fastmail.com/signup/",
               "Content-type": "application/json",
               "X-TrustedClient": "Yes",
               "Origin": "https://www.fastmail.com"}

    fastmailURL = "https://www.fastmail.com:443/jmap/setup/"
    sreq = req_session_fun()

    for fmdomain in fastmailLst:
        # print(fastmailLst.index(fmdomain)+1, fmdomain)

        fmmail = "{}@{}".format(target, fmdomain)

        fastmailJSON = {"methodCalls": [["Signup/getEmailAvailability", {"email": fmmail}, "0"]],
                        "using": ["https://www.fastmail.com/dev/signup"]}

        try:
            chkFastmail = await sreq.post(fastmailURL, headers=headers, json=fastmailJSON, timeout=5)

            async with chkFastmail:
                if chkFastmail.status == 200:
                    resp = await chkFastmail.json()
                    fmJson = resp['methodResponses'][0][1]['isAvailable']
                    if fmJson is False:
                        fastmailSucc.append("{}".format(fmmail))

        except Exception as e:
            logger.error(e, exc_info=True)

        sleep(random.uniform(0.5, 1.1))

    if fastmailSucc:
        result["Fastmail"] = fastmailSucc

    await sreq.close()

    return result


async def startmail(target, req_session_fun) -> Dict:  # TOR
    result = {}

    startmailURL = "https://mail.startmail.com:443/api/AvailableAddresses/{}%40startmail.com".format(target)
    headers = {"User-Agent": random.choice(uaLst),
               "X-Requested-With": "1.94.0"}
    sreq = req_session_fun()

    try:
        chkStartmail = await sreq.get(startmailURL, headers=headers, timeout=10)

        async with chkStartmail:
            if chkStartmail.status == 404:
                result["StartMail"] = "{}@startmail.com".format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def kolab(target, req_session_fun) -> Dict:
    result: Dict[str, List] = {}

    kolabLst = ["mykolab.com",
                "attorneymail.ch",
                "barmail.ch",
                "collaborative.li",
                "diplomail.ch",
                "freedommail.ch",
                "groupoffice.ch",
                "journalistmail.ch",
                "legalprivilege.ch",
                "libertymail.co",
                "libertymail.net",
                "mailatlaw.ch",
                "medicmail.ch",
                "medmail.ch",
                "mykolab.ch",
                "myswissmail.ch",
                "opengroupware.ch",
                "pressmail.ch",
                "swisscollab.ch",
                "swissgroupware.ch",
                "switzerlandmail.ch",
                "trusted-legal-mail.ch",
                "kolabnow.com",
                "kolabnow.ch"]

    ''' # old cool version ;(
    kolabURL = "https://kolabnow.com:443/cockpit/json.php"
    headers = { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0",
                "Referer": "https://kolabnow.com/cockpit/signup/individual",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"}

    try:
        kolabStatus = sreq.post(kolabURL, headers=headers)
        print(kolabStatus.status_code)

        if kolabStatus.status_code == 200:

            for kolabdomain in kolabLst:

                kolabPOST = {"validate": "username",
                            "accounttype": "individual",
                            "username": target,
                            "domain": kolabdomain,
                            "_action_": "/signup/validate"}

                try:

                    chkKolab = sreq.post(kolabURL, headers=headers, data=kolabPOST)

                    if chkKolab.status_code == 200:

                        kolabJSON = chkKolab.json()

                        if kolabJSON['errors']:
                            suc = "This email address is not available"
                            if kolabJSON['errors']['username'] == suc:
                                print("[+] Success with {}@{}".format(target, kolabdomain))

                except Exception as e:
                    pass

                sleep(random.uniform(1, 3))

    except Exception as e:
        #pass
        print e
    '''

    kolabURL = "https://kolabnow.com/api/auth/signup"
    headers = {"User-Agent": random.choice(uaLst),
               "Referer": "https://kolabnow.com/signup/individual",
               "Content-Type": "application/json;charset=utf-8",
               "X-Test-Payment-Provider": "mollie",
               "X-Requested-With": "XMLHttpRequest"}
    sreq = req_session_fun()

    kolabStatus = await sreq.post(kolabURL, headers={"User-Agent": random.choice(uaLst)}, timeout=10)

    if kolabStatus.status == 422:

        kolabpass = randstr(12)
        kolabsuc = "The specified login is not available."

        for kolabdomain in kolabLst:

            kolabPOST = {"login": target,
                         "domain": kolabdomain,
                         "password": kolabpass,
                         "password_confirmation": kolabpass,
                         "voucher": "",
                         "code": "bJDmpWw8sO85KlgSETPWtnViDgQ1S0MO",
                         "short_code": "VHBZX"}

            try:
                # chkKolab = sreq.post(kolabURL, headers=headers, data=kolabPOST)
                chkKolab = await sreq.post(kolabURL, headers=headers, data=json.dumps(kolabPOST), timeout=10)
                resp = await chkKolab.text()

                if chkKolab.status == 200:

                    kolabJSON = chkKolab.json()
                    if kolabJSON["errors"]["login"] == kolabsuc:
                        # print("[+] Success with {}@{}".format(target, kolabdomain))
                        pass
                    else:
                        if kolabJSON["errors"]:
                            print(kolabJSON["errors"])

            except Exception as e:
                logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def bigmir(target, req_session_fun) -> Dict:
    result = {}

    bigmirSucc = []
    bigmirMail = ["i.ua", "ua.fm", "email.ua"]
    sreq = req_session_fun()

    for maildomain in bigmirMail:
        try:
            bigmirChkJS = "https://passport.i.ua/js/free.js?15908746259240-xml"

            headers = {
                'Pragma': 'no-cache',
                'Origin': 'https://passport.i.ua',
                'User-Agent': random.choice(uaLst),
                'Content-Type': 'application/octet-stream',
                'Referer': 'https://passport.i.ua/registration/'
            }

            bm_data = "login={}@{}".format(target, maildomain)

            bigmirChk = await sreq.post(bigmirChkJS, headers=headers, data=bm_data, timeout=10)

            async with bigmirChk:
                if bigmirChk.status == 200:
                    exist = "'free': false"

                    resp = await bigmirChk.text()
                    if "'free': false" in resp:
                        bigmirSucc.append("{}@{}".format(target, maildomain))

            sleep(random.uniform(2, 4))

        except Exception as e:
            logger.error(e, exc_info=True)

    if bigmirSucc:
        result["Bigmir"] = bigmirSucc

    await sreq.close()

    return result


async def tutby(target, req_session_fun) -> Dict:  # Down
    result = {}

    smtp_check = code250('tut.by', target)
    if smtp_check:
        result['Tut.by'] = smtp_check[0]
        return result

    sreq = req_session_fun()

    try:
        target64 = str(base64.b64encode(target.encode()))
        tutbyChkURL = "https://profile.tut.by/requests/index.php"

        headers = {
            'Pragma': 'no-cache',
            'Origin': 'https://profile.tut.by',
            'User-Agent': random.choice(uaLst),
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'https://profile.tut.by/register.html',
            'X-Requested-With': 'XMLHttpRequest'
        }

        tutbyData = f"action=lgval&l={target64}"
        tutbyChk = await sreq.post(tutbyChkURL, headers=headers, data=tutbyData, timeout=10)

        if tutbyChk.status == 200:
            exist = '[{"success":true}]'
            resp = await tutbyChk.text()

            if exist == resp:
                result['Tut.by'] = '{}@tut.by'.format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def xmail(target, req_session_fun) -> Dict:
    result = {}

    sreq = req_session_fun()
    xmailURL = "https://xmail.net:443/app/signup/checkusername"
    headers = {"User-Agent": random.choice(uaLst),
               "Accept": "application/json, text/javascript, */*",
               "Referer": "https://xmail.net/app/signup",
               "Content-Type": "application/x-www-form-urlencoded",
               "X-Requested-With": "XMLHttpRequest",
               "Connection": "close"}

    xmailPOST = {"username": target, "firstname": '', "lastname": ''}

    try:
        xmailChk = await sreq.post(xmailURL, headers=headers, data=xmailPOST, timeout=10)

        async with xmailChk:
            resp = await xmailChk.json()
            if not resp['username']:
                result["Xmail"] = "{}@xmail.net".format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def ukrnet(target, req_session_fun) -> Dict:
    result = {}

    ukrnet_reg_urk = "https://accounts.ukr.net:443/registration"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"}

    sreq = req_session_fun()

    try:

        get_reg_ukrnet = await sreq.get(ukrnet_reg_urk, headers=headers, timeout=10)

        async with get_reg_ukrnet:
            if get_reg_ukrnet.status == 200:
                ukrnet_cookies = sreq.cookie_jar
                if ukrnet_cookies:
                    ukrnetURL = "https://accounts.ukr.net:443/api/v1/registration/reserve_login"
                    ukrnetPOST = {"login": target}

                    ukrnetChk = await sreq.post(ukrnetURL, headers=headers, json=ukrnetPOST, timeout=10)

                    async with ukrnetChk:
                        if ukrnetChk.status == 200:
                            resp = await ukrnetChk.json()
                            if not resp['available']:
                                result["UkrNet"] = "{}@ukr.net".format(target)
    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def runbox(target, req_session_fun) -> Dict:
    result = {}

    runboxSucc = []
    runboxLst = ["mailhost.work",
                 "mailhouse.biz",
                 "messagebox.email",
                 "offshore.rocks",
                 "rbox.co",
                 "rbox.me",
                 "rbx.email",
                 "rbx.life",
                 "rbx.run",
                 "rnbx.uk",
                 "runbox.at",
                 "runbox.biz",
                 "runbox.bz",
                 "runbox.ch",
                 "runbox.co",
                 "runbox.co.in",
                 "runbox.com",
                 "runbox.dk",
                 "runbox.email",
                 "runbox.eu",
                 "runbox.is",
                 "runbox.it",
                 "runbox.ky",
                 "runbox.li",
                 "runbox.me",
                 "runbox.nl",
                 "runbox.no",
                 "runbox.uk",
                 "runbox.us",
                 "xobnur.uk"]

    headers = {"User-Agent": random.choice(uaLst),
               "Origin": "https://runbox.com",
               "Referer": "https://runbox.com/signup?runbox7=1"}

    sreq = req_session_fun()
    for rboxdomain in runboxLst:

        data = {"type": "person", "company": "", "first_name": "", "last_name": "", "user": target,
                "userdomain": "domainyouown.com", "runboxDomain": rboxdomain, "password": "",
                "password_strength": "", "email_alternative": "", "phone_number_cellular": "",
                "referrer": "", "phone_number_home": "", "g-recaptcha-response": "",
                "h-captcha-response": "", "signup": "%A0Set+up+my+Runbox+account%A0",
                "av": "y", "as": "y", "domain": "", "accountType": "person", "domainType": "runbox",
                "account_number": "", "timezone": "undefined", "runbox7": "1"}

        chkRunbox = await sreq.post('https://runbox.com/signup/signup', headers=headers, data=data, timeout=5)

        if chkRunbox.status == 200:
            resp = await chkRunbox.text()
            if "The specified username is already taken" in resp:
                runboxSucc.append("{}@{}".format(target, rboxdomain))

        sleep(random.uniform(1, 2.1))

    if runboxSucc:
        result["Runbox"] = runboxSucc

    await sreq.close()

    return result


async def iCloud(target, req_session_fun) -> Dict:
    result: Dict[str, List] = {}

    domains = [
        'icloud.com',
        'me.com',
        'mac.com',
    ]

    sreq = req_session_fun()

    for domain in domains:
        email = f'{target}@{domain}'
        headers = {
            'User-Agent': random.choice(uaLst),
            'sstt': 'zYEaY3WeI76oAG%2BCNPhCiGcKUCU0SIQ1cIO2EMepSo8egjarh4MvVPqxGOO20TYqlbJI%2Fqs57WwAoJarOPukJGJvgOF7I7C%2B1jAE5vZo%2FSmYkvi2e%2Bfxj1od1xJOf3lnUXZlrnL0QWpLfaOgOwjvorSMJ1iuUphB8bDqjRzyb76jzDU4hrm6TzkvxJdlPCCY3JVTfAZFgXRoW9VlD%2Bv3VF3in1RSf6Er2sOS12%2FZJR%2Buo9ubA2KH9RLRzPlr1ABtsRgw6r4zbFbORaKTSVWGDQPdYCaMsM4ebevyKj3aIxXa%2FOpS6SHcx1KrvtOAUVhR9nsfZsaYfZvDa6gzpcNBF9domZJ1p8MmThEfJra6LEuc9ssZ3aWn9uKqvT3pZIVIbgdZARL%2B6SK1YCN7',
            'Content-Type': 'application/json',
        }

        data = {'id': email}
        check = await sreq.post('https://iforgot.apple.com/password/verify/appleid', headers=headers, data=json.dumps(data), allow_redirects=False, timeout=5)
        if check.headers and check.headers.get('Location', '').startswith('/password/authenticationmethod'):
            if not result:
                result = {'iCloud': []}
            result['iCloud'].append(email)

    await sreq.close()

    return result


async def duckgo(target, req_session_fun) -> Dict:
    result = {}

    duckURL = "https://quack.duckduckgo.com/api/auth/signup"

    headers = {"User-Agent": random.choice(uaLst), "Origin": "https://duckduckgo.com", "Sec-Fetch-Dest": "empty",
               "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site", "Te": "trailers", "Referer": "https://duckduckgo.com/"}

    data = {
        "code": (None, "01337"),
        "user": (None, target),
        "email": (None, "mail@example.com")

    }

    sreq = req_session_fun()

    try:
        checkDuck = await sreq.post(duckURL, headers=headers, data=data, timeout=5)

        resp = await checkDuck.text()
        # if checkDuck.json()['error'] == "unavailable_username":
        if "unavailable_username" in resp:
            result["DuckGo"] = "{}@duck.com".format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def ctemplar(target, req_session_fun) -> Dict:

    result = {}
    sreq = req_session_fun()

    ctURL = "https://api.ctemplar.com/auth/check-username/"
    ctJSON = {"username": target}

    headers = {"User-Agent": random.choice(uaLst),
               "Accept": "application/json, text/plain, */*",
               "Referer": "https://mail.ctemplar.com/",
               "Content-Type": "application/json",
               "Origin": "https://mail.ctemplar.com"}

    try:
        chkCT = await sreq.post(ctURL, headers=headers, json=ctJSON)

        if chkCT.status == 200:
            resp = await chkCT.json()
            ct_exists = resp['exists']
            if ct_exists:
                result["CTemplar"] = "{}@ctemplar.com".format(target)

    except Exception as e:
        logger.error(e, exc_info=True)

    await sreq.close()

    return result


async def hushmail(target, req_session_fun) -> Dict:

    result = {}

    hushDomains = ["hushmail.com", "hush.com", "therapyemail.com", "counselingmail.com", "therapysecure.com", "counselingsecure.com"]
    hushSucc = []
    sreq = req_session_fun()

    hush_ts = int(datetime.datetime.now().timestamp())

    hushURL = "https://secure.hushmail.com/signup/create?format=json"
    ref_header = "https://secure.hushmail.com/signup/?package=hushmail-for-healthcare-individual-5-form-monthly&source=website&tag=page_business_healthcare,btn_healthcare_popup_signup_individual&coupon_code="
    hush_UA = random.choice(uaLst)

    hushpass = randstr(15)

    for hushdomain in hushDomains:

        # hushpass = randstr(15)
        hush_ts = int(datetime.datetime.now().timestamp())

        headers = {"User-Agent": hush_UA,
                   "Accept": "application/json, text/javascript, */*; q=0.01",
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "X-Hush-Ajax-Start-Time": str(hush_ts), "X-Requested-With": "XMLHttpRequest",
                   "Origin": "https://secure.hushmail.com", "Referer": ref_header,
                   "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}

        data = {"hush_customerid": '', "hush_exitmethod": "GET",
                "skin": "bootstrap311", "hush_cc_country": '',
                "trial_mode": '', "parent": '', "parent_code": '',
                "coupon_code": '', "form_token": "6e1555a603f6e762a090e6f6b885122f_dabaddeadbee",
                "__hushform_extra_fields": '', "hush_username": target, "hush_domain": hushdomain,
                "hush_pass1": hushpass, "hush_pass2": hushpass,
                "hush_exitpage": "https://secure.hushmail.com/pay?package=hushmail-for-healthcare-individual-5-form-monthly",
                "package": "hushmail-for-healthcare-individual-5-form-monthly",
                "hush_reservation_code": '', "hush_customerid": '', "hush_tos": '', "hush_privacy_policy": '',
                "hush_additional_tos": '', "hush_email_opt_in": '', "isValidAjax": "newaccountform"}

        try:
            hushCheck = await sreq.post(hushURL, headers=headers, data=data, timeout=5)

            if hushCheck.status == 200:
                resp = await hushCheck.json()
                if "'{}' is not available".format(target) in resp['formValidation']['hush_username']:
                    hushMail = "{}@{}".format(target, hushdomain)
                    hushSucc.append(hushMail)

        except Exception as e:
            logger.error(e, exc_info=True)

        sleeper(hushDomains, 1.1, 2.2)

    if hushSucc:
        result["HushMail"] = hushSucc

    await sreq.close()

    return result

####################################################################################


def show_banner():
    banner = r"""

                  ,-.                    ^
                 ( (        _,---._ __  / \
                  ) )    .-'       `./ /   \
                 ( (   ,'            `/    /:
                  \ `-"             \'\   / |
                   .              ,  \ \ /  |
                   / @          ,'-`----Y   |
                  (            ;        :   :
                  |  .-.   _,-'         |  /
                  |  | (  (             | /
                  )  (  \  `.___________:/
                  `..'   `--' :mailcat:
    """
    for color, part in zip(range(75, 89), banner.split('\n')[1:]):
        print("\033[1;38;5;{}m{}\033[0m".format(color, part))
        sleep(0.1337)


async def print_results(checker, target, req_session_fun, is_verbose_mode):
    checker_name = checker.__name__
    if is_verbose_mode:
        print(f'Running {checker_name} checker for {target}...')

    res = await checker(target, req_session_fun)

    try:
        if not res:
            if is_verbose_mode:
                print(f'No results for {checker_name}')
            res = {}
    except Exception as e:
        print(f'Error while checking {checker_name}: {e}')
        return

    for provider, emails in res.items():
        print(f'\033[1;38;5;75m{provider}: \033[0m')
        if isinstance(emails, str):
            emails = [emails]
        for email in emails:
            print(f'*  {email}')


CHECKERS = [gmail, yandex, proton, mailRu,
            rambler, tuta, yahoo, outlook,
            zoho, eclipso, posteo, mailbox,
            firemail, fastmail, startmail,
            bigmir, tutby, xmail, ukrnet,
            runbox, iCloud, duckgo, hushmail,
            ctemplar]  # -kolab -lycos(false((( )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Mailcat",
    )
    parser.add_argument(
        '-p',
        '--provider',
        action="append",
        metavar='<mail providers names>',
        dest="providers",
        default=[],
        help="Specify one or more mail providers by name",
    )
    parser.add_argument(
        "username",
        nargs='*',
        metavar="USERNAME",
        help="One username to search emails by",
    )
    parser.add_argument(
        '-l',
        '--list',
        action="store_true",
        default=False,
        help="List all the supported providers",
    )
    parser.add_argument(
        '-s',
        '--silent',
        action="store_true",
        default=False,
        help="Hide wonderful mailcat intro animation",
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action="store_true",
        default=False,
        help="Verbose output about search progress.",
    )
    parser.add_argument(
        '-d',
        '--debug',
        action="store_true",
        default=False,
        help="Display checking errors.",
    )
    parser.add_argument(
        '--tor',
        action="store_true",
        default=False,
        help="Use Tor where you need it",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.WARNING)

    if not args.silent:
        show_banner()

    if args.list:
        print('Supported email providers: ')
        print('  ' + ', '.join(map(lambda f: f.__name__, CHECKERS)))

    target = args.username

    if len(target) != 1:
        print('Please, specify one username to search!')
        sys.exit(1)
    else:
        target = target[0]

    if "@" in target:
        target = target.split('@')[0]

    if args.providers:
        pset = set(args.providers)
        checkers = [c for c in CHECKERS if c.__name__ in pset]
        if not checkers:
            print(f'Can not find providers {", ".join(args.providers)}')
    else:
        checkers = CHECKERS

    if args.tor:
        req_session_fun = via_tor
        print('Using tor to make requests...')
    else:
        req_session_fun = simple_session

    jobs = asyncio.gather(*[print_results(checker, target, req_session_fun, args.verbose) for checker in checkers])

    asyncio.get_event_loop().run_until_complete(jobs)

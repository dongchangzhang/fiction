import os
import ast
import sys
import time
import logging
import logging.handlers
import requests

from lxml import etree
from configparser import ConfigParser

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

header = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/17.17134'}

def request(url, logger):
    sleep_time = 0.1
    info = '_ Requesting For ' + url
    logger.info(info)
    try:
        respond = requests.get(url, headers=header, timeout=5)
    except requests.exceptions.Timeout:
        info = 'N Timeout And Retry Url Is ' + url
        logger.warning(info)
        for i in range(1, 20):
            try:
                respond = requests.get(url, headers=header, timeout=5)
            except requests.exceptions.Timeout:
                info = 'N Timeout For ' + url + 'Wait For %ss Please!' % sleep_time
                logger.warning(info)
                time.sleep(sleep_time)
                sleep_time *= 2
                continue
            logger.info('Y ' + url)
            return respond
        logger.error('E Error in Request ' + url)
        return None
    logger.info('Y ' + url)
    return respond

def download(urls, output_name, logger):
    f = open(output_name, 'w')
    for url in urls:
        # first page 
        respond = request(url, logger)
        if respond is None:
            logger.error('E Exit At Position 2')
            exit(1)
        logger.info('Y ' + url + ' Yes')
        html = etree.HTML(respond.text)
        # title
        title = html.xpath('//div[@class="bookname"]/h1/text()')
        f.write('\n' + title[0] + '\n\n')
        # links for other pages
        links = list(html.xpath('//div[@class="text"]/a/@href'))[:-1]
        # first page
        text = html.xpath('//div[@id="content"]/text()')
        text = ''.join(text)
        text = text.replace('\u3000\u3000', '\n')
        f.write(text.strip())
        
        for link in links:
            respond = request(link, logger)
            if respond is None:
                logger.error('E Exit At Position 3')
                exit(1)
            logger.info('Y ' + link + ' Page Yes')
            html = etree.HTML(respond.text)
            text = html.xpath('//div[@id="content"]/text()')
            text = ''.join(text)
            text = text.replace('\u3000\u3000', '\n')
            f.write(text.strip())
    f.close()

def send(logger, which, paras):
    logger.info('Start To Send Book ' + which)
    mail_host, sender, receivers, mail_user, mail_pass = paras
    message = MIMEMultipart()
    message['From'] = sender
    message['To'] = receivers 
    subject = 'my fiction'
    message['Subject'] = Header(subject, 'utf-8')
    
    att = MIMEText(open(which, 'rb').read(), 'base64', 'utf-8')
    att["Content-Type"] = 'application/octet-stream'
    att["Content-Disposition"] = 'attachment; filename="%s"' % which
    message.attach(att)
    
    try:
        smtp = smtplib.SMTP() 
        smtp.connect(mail_host, 25) 
        smtp.starttls()
        smtp.login(mail_user,mail_pass)  
        smtp.sendmail(sender, receivers, message.as_string())
        smtp.quit()
        logger.info('Email Had Been Sended')
    except:
        logger.error("E Can Not Send Mail")
        exit(1)

def get_catalogue(targets, logger):
    for target in targets:
        title = target[0]
        catalogue = request(target[1], logger)
        if catalogue is None:
            logger.error('E Exit At Position 1')
            exit(1)

        html = etree.HTML(catalogue.text)
        links = html.xpath('//dd/a/@href')
        # write catalogue into txt
        output = os.path.join(sys.path[0], title + '-new' + '.txt')
        with open(output, 'w') as f:
            for link in links:
                f.write(link + '\n')

def update(targets, logger, paras):
    r = []
    logger.info('Start Update')
    for target in targets:
        old_file = os.path.join(sys.path[0], target[0] + '-old' + '.txt')
        new_file = os.path.join(sys.path[0], target[0] + '-new' + '.txt')
        old = []
        new = []
        if os.path.exists(old_file):
            with open(old_file, 'r') as f:
                old = [line.strip() for line in f if line.strip() != '']
        if os.path.exists(new_file):
            with open(new_file, 'r') as f:
                new = [line.strip() for line in f if line.strip() != '']
        else:
            logger.error('E Need ' + new_file)
            exit(1)
        logger.info('new is %s and old is %s' %(len(new), len(old)))
        if (len(new) <= len(old)):
            r.append(0)
            continue
        want = new[len(old):]
        r.append(len(want))
        # download
        output_name = os.path.join(sys.path[0], target[0] + '.txt')
        download(want, output_name, logger)
        send(logger, output_name, paras)
    return r
    
def run(targets, logger, paras, nu):
    new = True
    while True:
        if not new:
            logger.info('Sleep For %ss' % 300)
            time.sleep(300)
            logger.info('Start To Work')
        else:
            new = False
        status = None
        try:
            logger.info('get catalogue')
            get_catalogue(targets, logger)
            logger.info('update and download')
            status = update(targets, logger, paras)
        except:
            logger.error('Error In Action')
            continue
        logger.info('Action End')

        if status is None:
            continue

        if len(status) != nu: 
            logger.error('E Error in Downloads Times')
            continue

        for i in range(0, nu):
            target = targets[i]
            if status[i] <= 0:
                logger.info('None for ' + target[0])
                continue
            old_file = os.path.join(sys.path[0], target[0] + '-old' + '.txt')
            new_file = os.path.join(sys.path[0], target[0] + '-new' + '.txt')
            try:
                os.remove(old_file)
            except:
                logger.warning('Can Not Remove, No Such File ' + old_file)
            try:
                os.rename(new_file, old_file)
            except:
                logger.warning('Can Not Rename, No Such File ' + new_file)

if __name__ == '__main__':
    # info of config
    # load
    config_file = os.path.join(sys.path[0], 'fiction.conf')
    config = ConfigParser()
    config.read(config_file)
    # for download
    urls = ast.literal_eval(config.get('hunhun', 'fiction_url'))
    names = ast.literal_eval(config.get('hunhun', 'fiction_name_en'))
    nu = len(names)
    # zipped the values
    targets = [(names[i], urls[i]) for i in range(0, len(urls))]
    # for mail to kindle
    mail_host = config.get('mail', 'mail_host')
    sender = config.get('mail', 'sender')
    receiver = config.get('mail', 'receiver')
    mail_user = config.get('mail', 'mail_user')
    passwd = config.get('mail', 'passwd')
    # paras -- 4
    paras = (mail_host, sender, receiver, mail_user, passwd)
    # log
    logger = logging.getLogger("Fiction")
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')
    file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join(sys.path[0], "fiction-log-"), when='H', interval=2, backupCount=10)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.formatter = formatter
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
    
    # start running
    try:
        run(targets, logger, paras, nu)
    except:
        logger.error('Error In Position 0')

#-*- coding: UTF-8 -*-
import os.path,math,configparser,qrcode,time,tempfile,threading,requests
from PIL import Image,ImageFont,ImageDraw
from qiniu import Auth, put_file, etag, urlsafe_base64_encode
import qiniu.config

mHost = 'm.ys001.top'
iniFile = 'wx.ini'

maxLength = 32
qrMargin = 25
defImg = './res/default.jpg'
font1 = ImageFont.truetype('./res/simhei.ttf', 25)
font2 = ImageFont.truetype('./res/simhei.ttf', 48)
attWidth = 800

try:
    cf = configparser.ConfigParser()
    cf.read(iniFile)
    count = cf.getint('system', 'p')
except:
    count = 1

def isDoubleBytes(uchar):
    """判断一个unicode是否是汉字"""
    #if uchar >= u'\u4e00' and uchar <=u'\u9fa5':
    if uchar >= u'\u2E80' and uchar <=u'\uFFEF':
        return True
    else:
        return False

def reallen(strs):
    strs = strs.strip()
    length = len(strs)
    utf8_length = len(strs.encode('utf-8'))
    length = (utf8_length - length)/2 + length
    return int(length)

def strToArr(string, bytesLen):
    arr = []
    rLen = reallen(string)
    times = math.ceil(rLen/bytesLen)
    start = 0
    for i in range(times):
        end = int(start + bytesLen/2)
        if end > len(string):
            end = len(string)
        s = string[start:end]

        while reallen(s) < bytesLen:
            if len(s)==0 or end >= len(string):
                break
            end += 1
            s = string[start:end]
        start = end
        if len(s) == 0:
            break
        arr.append(s)

    return arr

def makeAttachImg(title, price, url):
    image = Image.open(defImg)
    draw = ImageDraw.Draw(image)

    l = strToArr(title, maxLength)
    #print(l)
    for i in range(len(l)):
        draw.text((325, 25+i*32), l[i], font=font1, fill=(0, 0, 0))
    draw.text((440, 115), price, font=font2, fill=(255, 0, 0))

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    xsize, ysize = img.size

    image.paste(img, (qrMargin, qrMargin, qrMargin + xsize, qrMargin + ysize))
    return image

def getImgFromUrl(url):
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        r.raw.decode_content = True
        img = Image.open(r.raw)
        r.close()
        return img
    except:
        return ''

def mergeImg(ewmImg, goodsImg):
    w1, h1 = ewmImg.size
    w, h = goodsImg.size
    if w > attWidth:
        h = math.ceil(attWidth/w*h)
        w = attWidth
        goodsImg.thumbnail((w, h))
    elif w < attWidth:
        h1 = math.ceil(w/w1*h1)
        w1 = w
        ewmImg.thumbnail((w1, h1))

    f = Image.new('RGB', (w, h+h1), (255, 255, 255))
    f.paste(goodsImg, (0, 0))
    f.paste(ewmImg, (0, h))
    return f

def makeGoodsImg(dt):
    imgurl = dt['pict_url'].strip()
    if imgurl == '':
        return ''

    if imgurl.startswith('//'):
        imgurl = 'https:'+imgurl

    title = dt['title'].strip()
    price = str(dt['sale_price']).strip()
    dlj = dt['dlj'].strip()
    ewmImg = makeAttachImg(title, price, dlj)

    goodsImg = getImgFromUrl(imgurl)
    if goodsImg == '':
        return ''

    localimg = tempfile.mktemp()+'.jpg'
    localimg = 'comment/'+os.path.basename(localimg)
    f = mergeImg(ewmImg, goodsImg)
    f.save(localimg, 'jpeg')
    f.close()
    goodsImg.close()
    ewmImg.close()

    return localimg

def getTuiJian(keywords, nums):
    dt = {'status':0, 'img':'', 'msg':''}

    _params = {'q':keywords, 'p':nums}
    url = 'http://' + mHost + '/taobao/f.php'
    r = requests.get(url, params=_params, allow_redirects=False)
    #print(r.status_code)
    if r.status_code != 200:
        return dt

    r.encoding = 'UTF-8'
    result = r.json()

    dt['status'] = result['status']
    if dt['status'] == 1:
        #dt['img'] = downimg(result['data']['pict_url'].strip())
        dt['img'] = makeGoodsImg(result['data'])
        dt['msg'] = result['data']['note'].strip()

    return dt

def tuijian(dt):
    #groupId = dt['groupId']
    ret = getTuiJian(dt['keywords'], dt['no'])
    
    if ret['status'] == 0:
        reSetIndex('1')
        return
    
    #print(ret)
    img = upToQiniu(ret['img'])
    print("%d)%s\n\n%s"%(dt['no'], img, ret['msg']))

def upToQiniu(key):
    #access_key = 'Xnfc0rJcCZfMC11I72CKUZwfwXQQD0jOGBplCs3O'
    #secret_key = 'oCus3WguKjaFqH85lF3wC3i4N43vVNL4-gb59Yar'
    access_key = 'iQdob5xuRsJK3K3lVYkjdbrHOYXJiyPMBXCiNBYx'
    secret_key = 'GLThz63eeZWIFNjXkYSKIqT8cXmwMI8znoiRJlRp'
    #构建鉴权对象
    q = Auth(access_key, secret_key)
    #要上传的空间
    bucket_name = 'eshouse'
    #上传到七牛后保存的文件名
    #key = 'tmpb9vtxnnm.jpg';
    #生成上传 Token，可以指定过期时间等
    token = q.upload_token(bucket_name, key, 3600)
    #要上传文件的本地路径
    localfile = key
    ret, info = put_file(token, key, localfile)
    #print(info)
    #assert ret['key'] == key
    #assert ret['hash'] == etag(localfile)

    return 'http://ov4b87mt3.bkt.clouddn.com/'+ret['key']

def reSetIndex(index):
    global count
    nIndex = int(index)
    if nIndex < 1:
        nIndex = 1

    count = nIndex

if __name__ == '__main__':
    dt = {}
    dt['no'] = count
    count += 1

    dt['keywords'] = ''
    t = threading.Thread(target=tuijian,args=(dt,))
    t.start()
    t.join(10)

    try:
        cf = configparser.ConfigParser()
        cf.read(iniFile)
        cf.set('system', 'p', str(count))
        with open(iniFile, 'w+') as f:
            cf.write(f)
    except:
        pass

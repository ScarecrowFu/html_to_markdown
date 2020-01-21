"""
desc:
    将html内容转为markdown内容, 图片上传到七牛
auth:
    Alan
requirements:
    pip install qiniu requests beautifulsoup4
how to use:
    查看README.md
"""
import re
import warnings
import random
from qiniu import Auth, put_file, etag, urlsafe_base64_encode
import os
import hashlib
import pathlib
import requests
import shutil
from mimetypes import guess_extension
from bs4 import BeautifulSoup
import configparser

# markdown 标签
MARKDOWN_ELEMENTS = {
    'h1': ('\n# ', '\n'),
    'h2': ('\n## ', '\n'),
    'h3': ('\n### ', '\n'),
    'h4': ('\n#### ', '\n'),
    'h5': ('\n##### ', '\n'),
    'h6': ('\n###### ', '\n'),
    'code': ('`', '`'),
    'ul': ('', ''),
    'ol': ('', ''),
    'li': ('- ', ''),
    'blockquote': ('\n> ', '\n'),
    'em': ('*', '*'),
    'strong': ('**', '**'),
    'block_code': ('\n```\n', '\n```\n'),
    'span': ('', ''),
    'p': ('\n', '\n'),
    'p_with_out_class': ('\n', '\n'),
    'inline_p': ('', ''),
    'inline_p_with_out_class': ('', ''),
    'b': ('**', '**'),
    'i': ('*', '*'),
    'del': ('~~', '~~'),
    'hr': ('\n---', '\n\n'),
    'thead': ('\n', '|------\n'),
    'tbody': ('\n', '\n'),
    'td': ('|', ''),
    'th': ('|', ''),
    'tr': ('', '\n'),
    'table': ('', '\n'),
    'e_p': ('', '\n')
}

# 外部标签
OUTLINE_ELEMENTS = {
    'h1': '<h1.*?>(.*?)</h1>',
    'h2': '<h2.*?>(.*?)</h2>',
    'h3': '<h3.*?>(.*?)</h3>',
    'h4': '<h4.*?>(.*?)</h4>',
    'h5': '<h5.*?>(.*?)</h5>',
    'h6': '<h6.*?>(.*?)</h6>',
    'hr': '<hr/>',
    'blockquote': '<blockquote.*?>(.*?)</blockquote>',
    'ul': '<ul.*?>(.*?)</ul>',
    'ol': '<ol.*?>(.*?)</ol>',
    # 'block_code': '<pre.*?><code.*?>(.*?)</code></pre>',
    'block_code': '<pre(.*?)>(.*?)</pre>',
    'p': '<p\s.*?>(.*?)</p>',
    'p_with_out_class': '<p>(.*?)</p>',
    'thead': '<thead.*?>(.*?)</thead>',
    'tr': '<tr.*?>(.*?)</tr>'
}

# 内嵌标签
INLINE_ELEMENTS = {
    'td': '<td.*?>((.|\n)*?)</td>',  # td element may span lines
    'tr': '<tr.*?>((.|\n)*?)</tr>',
    'th': '<th.*?>(.*?)</th>',
    'b': '<b.*?>(.*?)</b>',
    'i': '<i.*?>(.*?)</i>',
    'del': '<del.*?>(.*?)</del>',
    'inline_p': '<p\s.*?>(.*?)</p>',
    'inline_p_with_out_class': '<p>(.*?)</p>',
    'code': '<code.*?>(.*?)</code>',
    'span': '<span.*?>(.*?)</span>',
    'ul': '<ul.*?>(.*?)</ul>',
    'ol': '<ol.*?>(.*?)</ol>',
    'li': '<li.*?>(.*?)</li>',
    'img': '<img.*?src="(.*?)".*?>(.*?)</img>',
    'img_single': '<img.*?src="(.*?)".*?/>',
    'img_single_no_close': '<img.*?src="(.*?)".*?>',
    'a': '<a.*?href="(.*?)".*?>(.*?)</a>',
    'em': '<em.*?>(.*?)</em>',
    'strong': '<strong.*?>(\s*)(.*?)(\s*)</strong>',
    'tbody': '<tbody.*?>((.|\n)*)</tbody>',
}

# 需要删除的标签
DELETE_ELEMENTS = [
    '<span.*?>',
    '</span>',
    '<div.*?>',
    '</div>',
    '<br clear="none"/>',
    '<center.*?>',
    '</center>'
]

tmp_files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp_files')
md_files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'md_files')


# 生成随机headers
def rand_header():
    head_connection = ['Keep-Alive', 'close']
    head_accept = ['text/html, application/xhtml+xml, */*']
    head_accept_language = ['zh-CN,fr-FR;q=0.5', 'en-US,en;q=0.8,zh-Hans-CN;q=0.5,zh-Hans;q=0.3']
    head_user_agent = ['Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
                       'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36',
                       'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0; .NET4.0C; rv:11.0) like Gecko)',
                       'Mozilla/5.0 (Windows; U; Windows NT 5.2) Gecko/2008070208 Firefox/3.0.1',
                       'Mozilla/5.0 (Windows; U; Windows NT 5.1) Gecko/20070309 Firefox/2.0.0.3',
                       'Mozilla/5.0 (Windows; U; Windows NT 5.1) Gecko/20070803 Firefox/1.5.0.12',
                       'Opera/9.27 (Windows NT 5.2; U; zh-cn)',
                       'Mozilla/5.0 (Macintosh; PPC Mac OS X; U; en) Opera 8.0',
                       'Opera/8.0 (Macintosh; PPC Mac OS X; U; en)',
                       'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8.1.12) Gecko/20080219 Firefox/2.0.0.12 Navigator/9.0.0.6',
                       'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Win64; x64; Trident/4.0)',
                       'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0)',
                       'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0; InfoPath.2; .NET4.0C; .NET4.0E)',
                       'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Maxthon/4.0.6.2000 Chrome/26.0.1410.43 Safari/537.1 ',
                       'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0; InfoPath.2; .NET4.0C; .NET4.0E; QQBrowser/7.3.9825.400)',
                       'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:21.0) Gecko/20100101 Firefox/21.0 ',
                       'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.92 Safari/537.1 LBBROWSER',
                       'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0; BIDUBrowser 2.x)',
                       'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.11 TaoBrowser/3.0 Safari/536.11']

    header = {
        'Connection': head_connection[0],
        'Accept': head_accept[0],
        'Accept-Language': head_accept_language[1],
        'User-Agent': head_user_agent[random.randrange(0, len(head_user_agent))]
    }
    return header


# 七牛
class QiNiu(object):
    def __init__(self, access_key, secret_key, domain, bucket_name):
        self.access_key = access_key
        self.secret_key = secret_key
        self.auth = self.get_auth()
        self.token = None
        self.domain = domain
        self.bucket_name = bucket_name

    def get_auth(self):
        q = Auth(self.access_key, self.secret_key)
        return q

    def get_token(self, key_name):
        self.token = self.auth.upload_token(self.bucket_name, key_name, 3600)

    def upload_file(self, local_file, key_name=None):
        if not key_name:
            ext = pathlib.Path(local_file).suffix
            hash_name = self.hash_file(local_file)
            key_name = hash_name + ext
        if not self.token:
            self.get_token(key_name)
        ret, info = put_file(self.token, key_name, local_file)
        return ret, info

    def hash_file(self, local_file):
        hasher = hashlib.md5()
        with open(local_file, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def upload_url_file(self, pic_url, save_path):
        try:
            r = requests.get(pic_url, stream=True)
            if r.status_code == 200:
                guess = guess_extension(r.headers['content-type'])
                save_file = os.path.join(save_path, 'tmp' + guess)
                with open(save_file, 'wb') as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)
                ret, info = self.upload_file(save_file)
                if info.status_code == 200:
                    return self.domain+ret['key']
                else:
                    return None
        except:
            return pic_url


# 生成标签元素
class Element(object):
    def __init__(self, start_pos, end_pos, content, tag, class_=None, qu_niu=None):
        self.start_pos = start_pos  # 标签起始位置
        self.end_pos = end_pos  # 标签结束位置
        self.content = content.strip()  # 标签内容
        self.tag = tag  # 标签名称
        self.class_ = class_
        self.qi_niu = qu_niu
        self.parse_inline()  # 解析内嵌标签

    def __str__(self):
        # 返回markdown格式的内容/判断block_code情况
        if self.tag == 'block_code' and self.class_:
            try:
                lang_code = re.findall(r'class="brush:(.*?);toolbar:false"', self.class_)[0]
                wrapper = MARKDOWN_ELEMENTS.get(self.tag)
                self._result = '\n```{}\n{}{}'.format(lang_code, self.content, wrapper[1])
            except:
                wrapper = MARKDOWN_ELEMENTS.get(self.tag)
                self._result = '{}{}{}'.format(wrapper[0], self.content, wrapper[1])
        else:
            wrapper = MARKDOWN_ELEMENTS.get(self.tag)
            self._result = '{}{}{}'.format(wrapper[0], self.content, wrapper[1])
        return self._result

    # 解析主方法
    def parse_inline(self):
        # 转义字符
        self.content = self.content.replace('\r', '')  # windows \r character
        self.content = self.content.replace('\xc2\xa0', ' ')  # no break space
        self.content = self.content.replace('&quot;', '\"')  # html quote mark
        self.content = self.content.replace('&nbsp;', '')  # non-breaking space
        self.content = self.content.replace('&#39;', '\'')  # apostrophe
        self.content = self.content.replace('&lt;', '<')
        self.content = self.content.replace('&gt;', '>')

        if self.tag == "table":  # for removing tbody
            self.content = re.sub(INLINE_ELEMENTS['tbody'], '\g<1>', self.content)

        INLINE_ELEMENTS_LIST_KEYS = list(INLINE_ELEMENTS.keys())
        INLINE_ELEMENTS_LIST_KEYS.sort()
        for tag in INLINE_ELEMENTS_LIST_KEYS:
            pattern = INLINE_ELEMENTS[tag]

            if tag == 'a':
                self.content = re.sub(pattern, '[\g<2>](\g<1>)', self.content, count=re.M, flags=re.S)
            # 上传图片至七牛并返回url生成到markdown 文档
            elif tag == 'img':
                result = re.findall(pattern, self.content)
                if result:
                    try:
                        img_url = self.qi_niu.upload_url_file(pic_url=result[0][0], save_path=tmp_files_path)
                    except:
                        img_url = None
                    if img_url:
                        self.content = re.sub(pattern, '![\g<2>]({})'.format(img_url), self.content)
                    else:
                        self.content = re.sub(pattern, '![\g<2>](\g<1>)', self.content, count=re.M, flags=re.S)
                else:
                    self.content = re.sub(pattern, '![\g<2>](\g<1>)', self.content, count=re.M, flags=re.S)
            elif tag == 'img_single':
                result = re.findall(pattern, self.content)
                if result:
                    try:
                        img_url = self.qi_niu.upload_url_file(pic_url=result[0], save_path=tmp_files_path)
                    except:
                        img_url = None
                    if img_url:
                        self.content = re.sub(pattern, '![]({})'.format(img_url), self.content, count=re.M, flags=re.S)
                    else:
                        self.content = re.sub(pattern, '![](\g<1>)', self.content)
                else:
                    self.content = re.sub(pattern, '![](\g<1>)', self.content, count=re.M, flags=re.S)
            elif tag == 'img_single_no_close':
                result = re.findall(pattern, self.content)
                if result:
                    try:
                        img_url = self.qi_niu.upload_url_file(pic_url=result[0], save_path=tmp_files_path)
                    except:
                        img_url = None
                    if img_url:
                        self.content = re.sub(pattern, '![]({})'.format(img_url), self.content, count=re.M, flags=re.S)
                    else:
                        self.content = re.sub(pattern, '![](\g<1>)', self.content)
                else:
                    self.content = re.sub(pattern, '![](\g<1>)', self.content)
            elif self.tag == 'ul' and tag == 'li':
                self.content = re.sub(pattern, '- \g<1>', self.content)
            elif self.tag == 'ol' and tag == 'li':
                self.content = re.sub(pattern, '1. \g<1>', self.content)
            elif self.tag == 'thead' and tag == 'tr':
                self.content = re.sub(pattern, '\g<1>\n', self.content.replace('\n', ''))
            elif self.tag == 'tr' and tag == 'th':
                self.content = re.sub(pattern, '|\g<1>', self.content.replace('\n', ''))
            elif self.tag == 'tr' and tag == 'td':
                self.content = re.sub(pattern, '|\g<1>|', self.content.replace('\n', ''))
                self.content = self.content.replace("||", "|")  # end of column also needs a pipe
            elif self.tag == 'table' and tag == 'td':
                self.content = re.sub(pattern, '|\g<1>|', self.content)
                self.content = self.content.replace("||", "|")  # end of column also needs a pipe
                self.content = self.content.replace('|\n\n', '|\n')  # replace double new line
                self.construct_table()
            else:
                wrapper = MARKDOWN_ELEMENTS.get(tag)
                if tag == 'strong':
                    self.content = re.sub(pattern, '{}\g<2>{}'.format(wrapper[0], wrapper[1]), self.content)
                else:
                    self.content = re.sub(pattern, '{}\g<1>{}'.format(wrapper[0], wrapper[1]), self.content)

    # 生成markdown格式的table
    def construct_table(self):
        # this function, after self.content has gained | for table entries,
        # adds the |---| in markdown to create a proper table
        count = 1
        temp = self.content.split('\n', 3)
        for elt in temp:
            if elt != "":
                count = elt.count("|")  # count number of pipes
                break
        pipe = "\n|"  # beginning \n for safety
        for i in range(count - 1):
            pipe += "---|"
        pipe += "\n"
        self.content = pipe + pipe + self.content + "\n"  # TODO: column titles?
        self.content = self.content.replace('|\n\n', '|\n')  # replace double new line
        self.content = self.content.replace("<br/>\n", "<br/>")  # end of column also needs a pipe


class MarkdownMaker(object):
    def __init__(self, html='', folder='', file='', qi_niu=None):
        self.html = html  # actual data
        self.folder = folder
        self.file = file
        self.qi_niu = qi_niu

    def convert(self, html=''):
        if html == '':
            html = self.html
        # main function here
        elements = []
        for tag, pattern in OUTLINE_ELEMENTS.items():
            # re.I 忽略大小写/ re.M 多行模式/ re.S 即为'.'并且包括换行符在内的任意字符（'.'不包括换行符）
            for m in re.finditer(pattern, html, re.I | re.S | re.M):
                # now m contains the pattern without the tag
                if tag == 'block_code':
                    try:
                        content = ''.join(m.groups()[1])
                        class_ = m.groups()[0]
                    except:
                        content = ''.join(m.groups())
                        class_ = None
                else:
                    content = ''.join(m.groups())
                    class_ = None
                element = Element(start_pos=m.start(),
                                  end_pos=m.end(),
                                  content=content,
                                  tag=tag,
                                  class_=class_,
                                  qu_niu=self.qi_niu
                                  )
                can_append = True
                # 如果当前匹配的内容已在解析的elements组内的某一个element里，则无需添加至elements
                # 如果当前匹配的内容包含某个已解析在elements组内的某一个element, 则移除这个element,并将新匹配的内容添加至elements
                for e in elements:
                    if e.start_pos < m.start() and e.end_pos > m.end():
                        can_append = False
                    elif e.start_pos > m.start() and e.end_pos < m.end():
                        elements.remove(e)
                if can_append:
                    elements.append(element)
        # 根据起始位置对内容排序并拼接
        elements.sort(key=lambda element: element.start_pos)
        self._markdown = ''.join([str(e) for e in elements])

        # 删除指定标签内容
        for index, element in enumerate(DELETE_ELEMENTS):
            self._markdown = re.sub(element, '', self._markdown)

        return self._markdown

    @property
    def markdown(self):
        self.convert(self.html)
        return self._markdown

    def export(self, folder=False):
        if len(self.file) < 1:
            warnings.warn("file not specified, renamed to tmp.md")
            file = "tmp.md"
        else:
            file = self.file.replace('.html', '.md')  # rename to md
        if len(self.folder) < 2:
            warnings.warn("folder not specified, will save to pwd")
        elif not folder:
            file = self.folder + '/' + file
        else:  # if folder is specified
            file = folder + '/' + file
        f = open(file, 'w')
        f.write(self._markdown)
        f.close()


if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read('config.txt')
        access_key = config.get('QINIU', 'access_key')
        secret_key = config.get('QINIU', 'secret_key')
        domain = config.get('QINIU', 'domain')
        bucket_name = config.get('QINIU', 'bucket_name')
        upload_qiniu = True
    except Exception as error:
        upload_qiniu = False
        access_key, secret_key, domain, bucket_name = '', '', '', ''

    html_url = 'http://fualan.com/blog/article/12/'

    article = requests.get(html_url)
    soup = BeautifulSoup(article.text, "html.parser")
    article_content = soup.find("section", class_="article typo")

    if access_key and secret_key and domain and bucket_name:
        # 图片上传到七牛, 指定access_key, secret_key, bucket_name
        qi_niu = QiNiu(access_key='access_key',
                       secret_key='secret_key',
                       domain='http://domain/', bucket_name='bucket')
        markdown_content = MarkdownMaker(article_content.__str__(), qi_niu=qi_niu).markdown
        print(markdown_content)
    else:
        # 转换格式
        markdown_content = MarkdownMaker(article_content.__str__()).markdown
        print(markdown_content)



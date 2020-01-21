# 说明

将html内容转为markdown内容, 图片上传到七牛

# 安装依赖

```bash
pip install qiniu requests beautifulsoup4
```

# 使用方法

可选择是否配置 ```config.txt```

若配置 ```config.txt```,  请按以下方式编写配置文件

```
[QINIU]
access_key = access_key
secret_key = secret_key
domain = domain
bucket_name = bucket_name
```

更改 `html_url` 为你需要转换的网址
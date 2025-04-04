# CSIT 5930

## Crawl Part
- [x] Crawl the data from the website
- [x] Generate four parts of files:
- - [x] `index.json` - include  URL,ID and Last-Modified
- - [x] `relations.txt` - store the relationship between the URLs. Using the format **Parent-Child**
- - [x] `urls.txt` - store the URLs
- - [x] `pages/*.html` - store the raw HTML files

## Logic Part
- [x] Initial MySQL backend for Django
- [x] Design models for data persistence
- [x] inverted index table (high priority)
- [x] term table (high priority)
- [x] Page rank data model
- [x] Description generation
- [ ] TF/IDF implementation
- [ ] HITS implementation
- [ ] Search suggestion implementation
- [ ] Term encoder and vague matching
- [ ] Use Redis to cache search results

## Website Part
- [x] Main search page
- [x] Search result page
- [x] AI suggestion
- [x] Link Django to MySQL to manage crawled data
- [x] `Pages` page which should contain all pages crawled
- [x] Search history
- [ ] "Terms" page
- [ ] Prompt engineering of AI conclusion
- [ ] Output a log file for AI calls
- [ ] Show query position in page content
- [ ] **[Continuous]** better front-end design

## Others
- [ ] Evaluation of IR performance
- [ ] Fine-tune weights of TF/IDF, PR, HITS


## Updates
### **20250222**
Link spider to the database;
The spider can only insert website data into the database and cannot update the data currently;


### **20250215**

Link your django to local MySQL service!

About installing MySQL, please refer to [Orcale MySQL: installer](https://dev.mysql.com/downloads/installer/)

The username is hard-coded as `django`, database name as `search_engine`, port as `3306`

Please set your own mysql password in env variables, whose key is `MYSQL_PASSWORD`

For more details, please refer to `djangoProject/settings.py`

After configuring MySQL, please run:

```commandline
python manage.py migrate
```

for initialization of django database, it is suggested to create a superuser at your local project, please refer to [Create superuser](https://docs.djangoproject.com/en/5.1/intro/tutorial02/#introducing-the-django-admin).



### **20250214**

#### About running AI suggestion

AI suggestions require a pre-registered API of Alibaba Cloud Bailian platform (阿里云百炼). Which can be found here: [Aliyun Bailian](https://bailian.console.aliyun.com/)

The API key should look like `st-abcdefghij97f47c66f40a1bf8f90e32`, which should be put in env variables.

In conda (Anaconda/Miniconda), use:

```commandline
conda env config vars set ALIYUN_API_KEY=<YOUR API KEY>
conda deactivate
conda actiavte <YOUR CONDA ENV>
```

For setting env variable in other systems, refer to [Aliyun bailian doc: How to set env variables](https://help.aliyun.com/zh/model-studio/developer-reference/configure-api-key-through-environment-variables#61b16c64afwh8).


#### About website

Now default page (without child path) is routed to `/search` page.

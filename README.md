# WIKIDATA PARSE

Simple Parser to convert the files lexemes in json to sqlite

## Install

```shell
poetry install
```

## Format source

Claims <=> Statements
![](Lexeme_data_model.png)

https://www.mediawiki.org/wiki/Extension:WikibaseLexeme/Data_Model
https://doc.wikimedia.org/Wikibase/master/php/docs_topics_json.html


## Behavior

Some type of claims are skipped: media, time, quantity, ...

## Source file

Download lexeme file at: [https://dumps.wikimedia.org/wikidatawiki/entities/](https://dumps.wikimedia.org/wikidatawiki/entities/)


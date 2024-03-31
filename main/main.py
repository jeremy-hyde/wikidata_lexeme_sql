import time
import logging
import sqlite3
from typing import Dict

import msgspec

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(input_filepath: str, input_properties: str, output_file: str):
    logger.info("Init Database")
    con = init_database(output_file)
    # Init Json Decoder
    decoder = msgspec.json.Decoder()

    logger.info("Open Properties File")
    with open(input_properties, mode="r") as file:
        line = file.readline()
        parse_properties(con, decoder, line)

    logger.info("Open Lexeme File")
    with open(input_filepath, mode="r") as file:
        for n, line in enumerate(file, start=1):
            if line.strip() in ("[", "]"):
                # Skip first and last line
                logger.debug("Skip line {}".format(n))
                continue

            # logger.info("Parse line {}".format(n))
            parse_lexeme_line(con, decoder, n, line)

            if n % 100000 == 0:
                logger.info(f"Line: {n}")
                con.commit()

    con.commit()
    con.close()


def init_database(output_file: str):
    """
    Table based on https://doc.wikimedia.org/Wikibase/master/php/docs_topics_json.html
    The problem is the lexeme dump does not correspond to the description
    """
    con = sqlite3.connect(output_file)
    cur = con.cursor()

    # Properties used to describe claims
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS properties(property_id, label, description,
        CONSTRAINT pk_properties PRIMARY KEY (property_id))
        """
    )

    cur.execute(
        "CREATE TABLE IF NOT EXISTS lexeme(lexeme_id, title, pageid, ns, type, lexicalCategory, language, lastrevid, modified)"
    )

    # Lemma represent the lexeme word
    cur.execute("CREATE TABLE IF NOT EXISTS lemmas(lexeme_id, language, value)")

    # Forms are the forms the word can take.
    # Each form is described with grammaticalFeatures like: singular, plural, feminine, etc
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS forms(form_id, lexeme_id, language, value, grammaticalFeatures, 
        CONSTRAINT pk_forms PRIMARY KEY (form_id, language),
        CONSTRAINT fk_forms FOREIGN KEY (lexeme_id) REFERENCES lexeme (lexeme_id))
    """
    )

    # Senses are descriptions
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS senses(sense_id, lexeme_id, language, value, 
        CONSTRAINT pk_senses PRIMARY KEY (sense_id, language),
        CONSTRAINT fk_senses FOREIGN KEY (lexeme_id) REFERENCES lexeme (lexeme_id))
    """
    )

    # Claims are different representation and explanation of the lexeme like hyphenation, TODO
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS claims(claim_id, parent_id, property_id, datatype, value,
        CONSTRAINT pk_claims PRIMARY KEY (claim_id),
        CONSTRAINT fk_properties FOREIGN KEY (property_id) REFERENCES properties (property_id))
    """
    )
    return con


def parse_properties(con, decoder, line: str):
    cur = con.cursor()
    result = decoder.decode(line)

    for prop in result:
        try:
            property_id = prop["property"].split("/")[-1]
            cur.execute(
                "INSERT INTO properties VALUES (?, ?, ?)",
                (
                    property_id,
                    prop["propertyLabel"],
                    prop.get("propertyDescription"),
                ),
            )
        except Exception as ex:
            logger.exception(prop)
            raise ex


def parse_lexeme_line(con, decoder, line_number: int, line: str):
    """
    Remove ",\n" at the end of each line to process the file as jsonlines
    This way the whole file does not have to be loaded in memory
    """
    if line.endswith(",\n"):
        result = decoder.decode(line[:-2])
    else:
        result = decoder.decode(line)
    try:
        save(con, line_number, result)
    except Exception as ex:
        logger.exception(line[:-2])
        raise ex


def save(con, line_number: int, result: Dict):
    cur = con.cursor()

    # Check for missing keys
    keys = result.keys()
    expected_keys = (
        "id",
        "title",
        "pageid",
        "ns",
        "type",
        "lexicalCategory",
        "language",
        "lastrevid",
        "modified",
        "lemmas",
        "claims",
        "forms",
        "senses",
    )
    other_keys = keys - expected_keys
    if other_keys:
        logger.warning(f"Unexpected keys: {other_keys} at line: {line_number}")

    # Save line
    save_lexeme(cur, line_number, result)
    save_lemmas(cur, line_number, result)
    save_claims(cur, line_number, result["claims"], result["id"])
    save_forms(cur, line_number, result)
    save_senses(cur, line_number, result)


def save_lexeme(cur, line_number: int, result: Dict):
    cur.execute(
        "INSERT INTO lexeme VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            result["id"],
            result["title"],
            result["pageid"],
            result["ns"],
            result["type"],
            result["lexicalCategory"],
            result["language"],
            result["lastrevid"],
            result["modified"],
        ),
    )


def save_lemmas(cur, line_number: int, result: Dict):
    for n, lemma in enumerate(iter(result["lemmas"].values()), start=1):
        logger.debug(f"Lemma n°{n} at line n°{line_number}")
        cur.execute(
            "INSERT INTO lemmas VALUES (?, ?, ?)",
            (result["id"], lemma["language"], lemma["value"]),
        )


def save_claims(cur, line_number: int, claims: Dict, parent_id: str):
    for m, claim in enumerate(iter(claims.values()), start=1):
        logger.debug(f"Claim n°{m} at line n°{line_number}")

        for o, sub_claim in enumerate(claim, start=1):
            logger.debug(f"Sub Claim n°{o} at line n°{line_number}")

            # Skip empty values
            if sub_claim["mainsnak"]["snaktype"] in ("novalue", "somevalue"):
                logger.debug(f"Sub Claim n°{o} at line n°{line_number} has no value => skipped")
                continue

            # Skip media: audio, video, time, quantity
            if sub_claim["mainsnak"]["datatype"] in ("commonsMedia", "time", "quantity"):
                logger.debug(f"Sub Claim n°{o} at line n°{line_number} is a media => skipped")
                continue

            # Adaptation to value types
            value = sub_claim["mainsnak"]["datavalue"]["value"]

            # For reference to other wikibase: wikibase-item, wikibase-form, wikibase-
            if sub_claim["mainsnak"]["datatype"].startswith("wikibase-"):
                value = sub_claim["mainsnak"]["datavalue"]["value"]["id"]

            if sub_claim["mainsnak"]["datatype"] == "monolingualtext":
                value = sub_claim["mainsnak"]["datavalue"]["value"]["text"]
                # TODO does not save the language present with this property, to fix

            if sub_claim.get("references"):
                logger.debug(f"Sub Claim n°{o} at line n°{line_number} has reference that skipped")

            cur.execute(
                f"INSERT INTO claims VALUES (?, ?, ?, ?, ?)",
                (
                    sub_claim["id"],
                    parent_id,
                    sub_claim["mainsnak"]["property"],
                    sub_claim["mainsnak"]["datatype"],
                    value,
                ),
            )


def save_forms(cur, line_number: int, result: Dict):
    for n, form in enumerate(result["forms"], start=1):
        logger.debug(f"Form n°{n} at line n°{line_number}")
        grammatical_features = ", ".join(form["grammaticalFeatures"])
        for m, repre in enumerate(iter(form["representations"].values()), start=1):
            logger.debug(f"Representation n°{m} at line n°{line_number}")
            cur.execute(
                "INSERT INTO forms VALUES (?, ?, ?, ?, ?)",
                (form["id"], result["id"], repre["language"], repre["value"], grammatical_features),
            )

        save_claims(cur, line_number, form["claims"], form["id"])


def save_senses(cur, line_number: int, result: Dict):
    for n, sense in enumerate(result["senses"], start=1):
        logger.debug(f"Sens n°{n} at line n°{line_number}")

        for m, lang in enumerate(iter(sense["glosses"].values()), start=1):
            logger.debug(f"language n°{m} at line n°{line_number}")
            cur.execute(
                "INSERT INTO senses VALUES (?, ?, ?, ?)",
                (sense["id"], result["id"], lang["language"], lang["value"]),
            )

        save_claims(cur, line_number, sense["claims"], sense["id"])


if __name__ == "__main__":
    now = time.time()
    logger.info("Start")
    main("latest-lexemes.json", "properties.json", "output.db")
    then = time.time()
    elapse = round(then - now, 3)
    logger.info(f"Took: {elapse} s")

from characters import CHARACTERS
from character import SheetAIMLCharacter
import json
import logging
import server
import requests
from collections import defaultdict
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

SUCCESS=0
WRONG_CHARACTER_NAME=1
NO_PATTERN_MATCH=2

useSOLR = True
CWD = os.path.dirname(os.path.realpath(__file__))

logger = logging.getLogger('hr.chatbot.server.chatbot')

def get_character(id, create=False):
    for character in CHARACTERS:
        if character.id == id:
            return character
    if create:
        character = SheetAIMLCharacter(id, 'sophia', 1)
        character.set_property_file(os.path.join(
            CWD, '..', '..', 'character_aiml', 'sophia.properties'))
        CHARACTERS.append(character)
        logger.info("Create SheetAIMLCharacter {}".format(character))
        return character

def is_local_character(character):
    if isinstance(character, server.character.SheetAIMLCharacter) or \
            isinstance(character, SheetAIMLCharacter):
        return False
    return True

def get_characters_by_name(name, local=True):
    characters = [c for c in CHARACTERS if c.name == name]
    if local:
        characters = [c for c in characters if is_local_character(c)]
    return characters

def list_character():
    return [c.id for c in CHARACTERS]

def update_character(id, csv_version=None):
    character = get_character(id)
    if not character:
        return False, "Character {} is not found".format(id)
    if isinstance(character, server.character.SheetAIMLCharacter) or \
            isinstance(character, SheetAIMLCharacter):
        try:
            character.load_csv_files(csv_version)
        except Exception as ex:
            logger.error(ex)
            return False, "Update {} failed\n{}".format(id, ex)
        return True, "{} is updated".format(id)
    else:
        return False, "Character {} doesn't support update".format(id)
    return False

def load_sheet_keys(id, sheet_keys):
    character = get_character(id, True)
    if not character:
        return False, "Character {} is not found".format(id)
    if not sheet_keys:
        return False, "No sheet key is set"
    if isinstance(character, server.character.SheetAIMLCharacter) or \
            isinstance(character, SheetAIMLCharacter):
        return character.load_sheet_keys(sheet_keys)
    else:
        return False, "Character doesn't support sheet keys"
    return False, "Unknown error"

def commit_character(id):
    character = get_character(id)
    if not character:
        return False, "Character {} is not found".format(id)
    if isinstance(character, server.character.SheetAIMLCharacter) or \
            isinstance(character, SheetAIMLCharacter):
        return character.commit()
    else:
        return False, "Character {} doesn't support committing".format(character)

responses = defaultdict(list)
max_chat_tries = 5
def _ask_characters(characters, question, session):
    chat_tries = 0
    last_response = None
    while True:
        chat_tries += 1
        for c in characters:
            _response = c.respond(question, session)
            assert isinstance(_response, dict), "Response must be a dict"
            answer = _response.get('text', None)
            if answer:
                last_response = _response
                if answer not in responses[question]:
                    responses[question].append(answer)
                    return _response
        if chat_tries > max_chat_tries:
            logger.warn('Maximum tries.')
            return last_response

def ask(id, question, session=None):
    """
    return (response dict, return code)
    """
    response = {'text': '', 'emotion': '', 'botid': '', 'botname': ''}
    character = get_character(id)
    if not character:
        return response, WRONG_CHARACTER_NAME

    # current character > local character with the same name > solr > generic character
    responding_characters = get_characters_by_name(character.name, local=True)
    if character in responding_characters:
        responding_characters.remove(character)
    responding_characters = sorted(responding_characters, key=lambda x: x.level)
    responding_characters.insert(0, character)

    if useSOLR:
        solr_character = get_character('solr_bot')
        if solr_character:
            responding_characters.append(solr_character)
        else:
            logger.warn("Solr character is not found")
    logger.info("Responding characters {}".format(responding_characters))

    _response = _ask_characters(responding_characters, question, session)

    if _response is None:
        generic = get_character('generic')
        if generic:
            generic.set_properties(character.get_properties())
            _response = _ask_characters([generic], question, session)
        else:
            logger.warn("Generic character is not found")

    if _response is not None:
        response.update(_response)
        logger.info("Ask {}, response {}".format(question, response))
        return response, SUCCESS
    else:
        return response, NO_PATTERN_MATCH

if __name__ == '__main__':
    for character in CHARACTERS:
        print ask(character.id, 'what is your name')


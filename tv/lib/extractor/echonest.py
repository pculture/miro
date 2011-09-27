#!/usr/bin/python

import logging 
import sys
import os

import pyechonest.config as config
import pyechonest.song as song

from miro import app
from miro.metadata import ExtractorInvalid
from miro.descriptions import (Artist, Label, File, DataSource,
        DataSourceStatus, Record)

config.ECHO_NEST_API_KEY = "BIHVIATV5MH3C4JXN"
config.CODEGEN_BINARY_OVERRIDE = "../linux/contrib/echoprint-codegen/codegen.Linux-x86_64"

_echonest = None
def _get_echonest_datasource():
    # TODO: better way to do this?
    global _echonest
    if _echonest is None:
        _echonest = DataSource.with_values(
            name=u'echonest', version=1, priority=80)
        DataSourceStatus.with_values(datasource=_echonest,
                description_type='File')
    return _echonest

def process(file_):
    """Yield descriptions to apply to whatever LibraryItem has the given path."""
    try:
        fp = song.util.codegen(file_.path, start=0, duration=30)
    except Exception:
        logging.exception('no echonest-codegen available ?')
        raise ExtractorInvalid

    # create a Record to document how and when the data was acquired
    record = Record(_get_echonest_datasource())

    if len(fp) and "code" in fp[0]:

        # The version parameter to song/identify indicates the use of echoprint
#        result = song.identify(query_obj=fp, version="4.11", buckets=['images'])
        try:
            result = song.identify(query_obj=fp, version="4.11")
        except IOError, e:
            logging.error(e)
            return

        if len(result):
            yield Artist.with_values(echonest_id=result[0].artist_id,
                    name=result[0].artist_name, record=record)
            yield Label.with_values(title=result[0].title, record=record)
#            yield Track.with_values(echonest_id=result[0].id, record=record)
            logging.debug("Echonest: got data for %s", file_.path)
        else:
            logging.warn("Echonest: no match for %s", file_.path)
    else:
        logging.warn("Echonest: couldn't decode %s", file_.path)

app.metadata_manager.add_provider(_get_echonest_datasource(), File, process)

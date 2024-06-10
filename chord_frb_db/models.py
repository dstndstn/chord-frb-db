from sqlalchemy.orm import DeclarativeBase
from typing import List
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, String, SmallInteger, BigInteger, Double, REAL, ForeignKey, Float

import numpy as np

class Base(DeclarativeBase):
    pass

# Note -- float32 = REAL
#         float64 = Double
#         int16   = SmallInteger
#         int32   = Integer
#         int64   = BigInteger

class Event(Base):
    __tablename__ = 'event'
    event_id:  Mapped[int] = mapped_column(primary_key=True)
    # ... FRB time at infinite frequency?  What time format?  Seconds since 1970.0
    timestamp: Mapped[float] = mapped_column(Double)
    is_rfi:    Mapped[bool]
    # matches a known source (Pulsar / Repeating FRB?)
    is_known:  Mapped[bool]
    is_frb:    Mapped[bool]

    # ??
    best_beam: Mapped[int] = mapped_column(SmallInteger)
    nbeams:    Mapped[int] = mapped_column(SmallInteger)
    beams:     Mapped[List['EventBeam']] = relationship(back_populates='event')
    best_snr:  Mapped[float] = mapped_column(REAL)
    # multi-beam
    total_snr: Mapped[float] = mapped_column(REAL)

    dm:        Mapped[float] = mapped_column(REAL)
    dm_error:  Mapped[float] = mapped_column(REAL)
    # in deg
    ra:        Mapped[float] = mapped_column(REAL)
    ra_error:  Mapped[float] = mapped_column(REAL)
    # in deg
    dec:       Mapped[float] = mapped_column(REAL)
    dec_error: Mapped[float] = mapped_column(REAL)

    dm_ne2001:  Mapped[float] = mapped_column(REAL)
    dm_ymw2016: Mapped[float] = mapped_column(REAL)
    
    spectral_index: Mapped[float] = mapped_column(REAL)
    scattering:     Mapped[float] = mapped_column(REAL)
    # in Jy-ms
    fluence:        Mapped[float] = mapped_column(REAL)
    # in Jy
    flux:           Mapped[float] = mapped_column(REAL)
    # in millisec
    pulse_width:    Mapped[float] = mapped_column(REAL)

    # Best known source match
    known_id:       Mapped[int] = mapped_column(ForeignKey('known_source.id'))
    known:     Mapped['KnownSource'] = relationship(back_populates='events')

    #def __repr__(self) -> str:
    #    return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"

# Individual-beam measurements for a grouped multi-beam event
class EventBeam(Base):
    __tablename__ = 'event_beam'
    id:   Mapped[int] = mapped_column(BigInteger, primary_key=True)
    beam: Mapped[int]

    best_snr:  Mapped[float] = mapped_column(REAL)

    timestamp: Mapped[float] = mapped_column(Double)

    dm:        Mapped[float] = mapped_column(REAL)
    dm_error:  Mapped[float] = mapped_column(REAL)

    ra:        Mapped[float] = mapped_column(REAL)
    ra_error:  Mapped[float] = mapped_column(REAL)

    dec:       Mapped[float] = mapped_column(REAL)
    dec_error: Mapped[float] = mapped_column(REAL)

    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    event:     Mapped['Event'] = relationship(back_populates='beams')

class KnownSource(Base):
    __tablename__ = 'known_source'
    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    ra:   Mapped[float] = mapped_column(REAL)
    dec:  Mapped[float] = mapped_column(REAL)
    dm:   Mapped[float] = mapped_column(REAL)
    events: Mapped[List['Event']] = relationship(back_populates='known')

if __name__ == '__main__':
    import os
    from sqlalchemy import create_engine

    # db_url = 'postgresql+psycopg2://frb:PASSWORD@localhost:5432/frb'
    # db_pass = os.environ.get('CHORD_FRB_DB_PASSWORD', 'PASSWORD')
    # db_url = db_url.replace('PASSWORD', db_pass)

    #db_url = "sqlite+pysqlite:///:memory:"
    db_url = "sqlite+pysqlite:///db.sqlite3"
    
    engine = create_engine(db_url, echo=True)

    Base.metadata.create_all(engine)




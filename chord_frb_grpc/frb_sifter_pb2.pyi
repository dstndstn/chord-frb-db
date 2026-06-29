from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProtocolVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
PROTOCOL_VERSION_UNSPECIFIED: _ClassVar[ProtocolVersion]
PROTOCOL_VERSION_CURRENT: _ClassVar[ProtocolVersion]

class ConfigMessage(_message.Message):
    __slots__ = ("protocol_version", "pirate_yaml", "xengine_yaml", "dedispersion_plan_yaml", "grouper_yaml")
    PROTOCOL_VERSION_FIELD_NUMBER: _ClassVar[int]
    PIRATE_YAML_FIELD_NUMBER: _ClassVar[int]
    XENGINE_YAML_FIELD_NUMBER: _ClassVar[int]
    DEDISPERSION_PLAN_YAML_FIELD_NUMBER: _ClassVar[int]
    GROUPER_YAML_FIELD_NUMBER: _ClassVar[int]
    protocol_version: int
    pirate_yaml: str
    xengine_yaml: str
    dedispersion_plan_yaml: str
    grouper_yaml: str
    def __init__(self, protocol_version: _Optional[int] = ..., pirate_yaml: _Optional[str] = ..., xengine_yaml: _Optional[str] = ..., dedispersion_plan_yaml: _Optional[str] = ..., grouper_yaml: _Optional[str] = ...) -> None: ...

class ConfigReply(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class FrbEvent(_message.Message):
    __slots__ = ("beam_id", "fpga_timestamp", "dm", "dm_error", "snr", "rfi_prob")
    BEAM_ID_FIELD_NUMBER: _ClassVar[int]
    FPGA_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DM_FIELD_NUMBER: _ClassVar[int]
    DM_ERROR_FIELD_NUMBER: _ClassVar[int]
    SNR_FIELD_NUMBER: _ClassVar[int]
    RFI_PROB_FIELD_NUMBER: _ClassVar[int]
    beam_id: int
    fpga_timestamp: int
    dm: float
    dm_error: float
    snr: float
    rfi_prob: float
    def __init__(self, beam_id: _Optional[int] = ..., fpga_timestamp: _Optional[int] = ..., dm: _Optional[float] = ..., dm_error: _Optional[float] = ..., snr: _Optional[float] = ..., rfi_prob: _Optional[float] = ...) -> None: ...

class FrbEventsMessage(_message.Message):
    __slots__ = ("has_injections", "beam_set_id", "chunk_fpga_count", "events", "coarsegrain_start_fpga_count", "coarsegrain_end_fpga_count", "coarsegrain_snr")
    HAS_INJECTIONS_FIELD_NUMBER: _ClassVar[int]
    BEAM_SET_ID_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FPGA_COUNT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    COARSEGRAIN_START_FPGA_COUNT_FIELD_NUMBER: _ClassVar[int]
    COARSEGRAIN_END_FPGA_COUNT_FIELD_NUMBER: _ClassVar[int]
    COARSEGRAIN_SNR_FIELD_NUMBER: _ClassVar[int]
    has_injections: bool
    beam_set_id: int
    chunk_fpga_count: int
    events: _containers.RepeatedCompositeFieldContainer[FrbEvent]
    coarsegrain_start_fpga_count: int
    coarsegrain_end_fpga_count: int
    coarsegrain_snr: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, has_injections: bool = ..., beam_set_id: _Optional[int] = ..., chunk_fpga_count: _Optional[int] = ..., events: _Optional[_Iterable[_Union[FrbEvent, _Mapping]]] = ..., coarsegrain_start_fpga_count: _Optional[int] = ..., coarsegrain_end_fpga_count: _Optional[int] = ..., coarsegrain_snr: _Optional[_Iterable[float]] = ...) -> None: ...

class FrbEventsReply(_message.Message):
    __slots__ = ("ok", "message")
    OK_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    message: str
    def __init__(self, ok: bool = ..., message: _Optional[str] = ...) -> None: ...

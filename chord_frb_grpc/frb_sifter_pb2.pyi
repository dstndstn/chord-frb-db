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
PROTOCOL_VERSION_UNSPECIFIED: ProtocolVersion
PROTOCOL_VERSION_CURRENT: ProtocolVersion

class ConfigMessage(_message.Message):
    __slots__ = ("protocol_version", "pirate_yaml", "xengine_yaml", "dedispersion_plan_yaml", "grouper_yaml", "search_ip_addr")
    PROTOCOL_VERSION_FIELD_NUMBER: _ClassVar[int]
    PIRATE_YAML_FIELD_NUMBER: _ClassVar[int]
    XENGINE_YAML_FIELD_NUMBER: _ClassVar[int]
    DEDISPERSION_PLAN_YAML_FIELD_NUMBER: _ClassVar[int]
    GROUPER_YAML_FIELD_NUMBER: _ClassVar[int]
    SEARCH_IP_ADDR_FIELD_NUMBER: _ClassVar[int]
    protocol_version: int
    pirate_yaml: str
    xengine_yaml: str
    dedispersion_plan_yaml: str
    grouper_yaml: str
    search_ip_addr: str
    def __init__(self, protocol_version: _Optional[int] = ..., pirate_yaml: _Optional[str] = ..., xengine_yaml: _Optional[str] = ..., dedispersion_plan_yaml: _Optional[str] = ..., grouper_yaml: _Optional[str] = ..., search_ip_addr: _Optional[str] = ...) -> None: ...

class ConfigReply(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: _Optional[bool] = ...) -> None: ...

class FrbEvent(_message.Message):
    __slots__ = ("beam_id", "fpga_timestamp", "dm", "snr", "rfi_prob", "width_ms", "subband_freq_lo_MHz", "subband_freq_hi_MHz")
    BEAM_ID_FIELD_NUMBER: _ClassVar[int]
    FPGA_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DM_FIELD_NUMBER: _ClassVar[int]
    SNR_FIELD_NUMBER: _ClassVar[int]
    RFI_PROB_FIELD_NUMBER: _ClassVar[int]
    WIDTH_MS_FIELD_NUMBER: _ClassVar[int]
    SUBBAND_FREQ_LO_MHZ_FIELD_NUMBER: _ClassVar[int]
    SUBBAND_FREQ_HI_MHZ_FIELD_NUMBER: _ClassVar[int]
    beam_id: int
    fpga_timestamp: int
    dm: float
    snr: float
    rfi_prob: float
    width_ms: float
    subband_freq_lo_MHz: float
    subband_freq_hi_MHz: float
    def __init__(self, beam_id: _Optional[int] = ..., fpga_timestamp: _Optional[int] = ..., dm: _Optional[float] = ..., snr: _Optional[float] = ..., rfi_prob: _Optional[float] = ..., width_ms: _Optional[float] = ..., subband_freq_lo_MHz: _Optional[float] = ..., subband_freq_hi_MHz: _Optional[float] = ...) -> None: ...

class FrbEventsMessage(_message.Message):
    __slots__ = ("from_simulator", "beam_set_id", "chunk_fpga_start", "chunk_fpga_end", "events", "coarsegrain_snr")
    FROM_SIMULATOR_FIELD_NUMBER: _ClassVar[int]
    BEAM_SET_ID_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FPGA_START_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FPGA_END_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    COARSEGRAIN_SNR_FIELD_NUMBER: _ClassVar[int]
    from_simulator: bool
    beam_set_id: int
    chunk_fpga_start: int
    chunk_fpga_end: int
    events: _containers.RepeatedCompositeFieldContainer[FrbEvent]
    coarsegrain_snr: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, from_simulator: _Optional[bool] = ..., beam_set_id: _Optional[int] = ..., chunk_fpga_start: _Optional[int] = ..., chunk_fpga_end: _Optional[int] = ..., events: _Optional[_Iterable[_Union[FrbEvent, _Mapping]]] = ..., coarsegrain_snr: _Optional[_Iterable[float]] = ...) -> None: ...

class FrbEventsReply(_message.Message):
    __slots__ = ("ok", "message")
    OK_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    message: str
    def __init__(self, ok: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...

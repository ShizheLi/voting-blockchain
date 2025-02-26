# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: blockchain.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'blockchain.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x10\x62lockchain.proto\x12\nblockchain\">\n\x0cRegistration\x12\x0f\n\x07version\x18\x01 \x01(\x05\x12\x0c\n\x04time\x18\x02 \x01(\x03\x12\x0f\n\x07\x61\x64\x64r_me\x18\x03 \x01(\t\"W\n\x10HandshakeRequest\x12\x0f\n\x07version\x18\x01 \x01(\x05\x12\x0c\n\x04time\x18\x02 \x01(\x03\x12\x0f\n\x07\x61\x64\x64r_me\x18\x03 \x01(\t\x12\x13\n\x0b\x62\x65st_height\x18\x04 \x01(\x05\"9\n\x08NodeList\x12\x16\n\x0enode_addresses\x18\x01 \x03(\t\x12\x15\n\rregistry_data\x18\x02 \x01(\x0c\"C\n\x0eNewTransaction\x12\x17\n\x0fserialized_data\x18\x01 \x01(\x0c\x12\x18\n\x10transaction_hash\x18\x02 \x01(\t\"7\n\x08NewBlock\x12\x17\n\x0fserialized_data\x18\x01 \x01(\x0c\x12\x12\n\nblock_hash\x18\x02 \x01(\t\"5\n\x11\x42roadcastResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t2P\n\x0cNodeRegistry\x12@\n\x0cRegisterNode\x12\x18.blockchain.Registration\x1a\x14.blockchain.NodeList\"\x00\x32\xf8\x01\n\x0f\x46ullNodeService\x12\x41\n\tHandshake\x12\x1c.blockchain.HandshakeRequest\x1a\x14.blockchain.NodeList\"\x00\x12V\n\x17NewTransactionBroadcast\x12\x1a.blockchain.NewTransaction\x1a\x1d.blockchain.BroadcastResponse\"\x00\x12J\n\x11NewBlockBroadcast\x12\x14.blockchain.NewBlock\x1a\x1d.blockchain.BroadcastResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'blockchain_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_REGISTRATION']._serialized_start=32
  _globals['_REGISTRATION']._serialized_end=94
  _globals['_HANDSHAKEREQUEST']._serialized_start=96
  _globals['_HANDSHAKEREQUEST']._serialized_end=183
  _globals['_NODELIST']._serialized_start=185
  _globals['_NODELIST']._serialized_end=242
  _globals['_NEWTRANSACTION']._serialized_start=244
  _globals['_NEWTRANSACTION']._serialized_end=311
  _globals['_NEWBLOCK']._serialized_start=313
  _globals['_NEWBLOCK']._serialized_end=368
  _globals['_BROADCASTRESPONSE']._serialized_start=370
  _globals['_BROADCASTRESPONSE']._serialized_end=423
  _globals['_NODEREGISTRY']._serialized_start=425
  _globals['_NODEREGISTRY']._serialized_end=505
  _globals['_FULLNODESERVICE']._serialized_start=508
  _globals['_FULLNODESERVICE']._serialized_end=756
# @@protoc_insertion_point(module_scope)

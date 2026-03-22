import requests, json, binascii, time, urllib3, base64, datetime, re, socket, threading, random, os, asyncio
from protobuf_decoder.protobuf_decoder import Parser
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Key, Iv = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56]), bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

async def EnC_AEs(HeX):
    cipher = AES.new(Key, AES.MODE_CBC, Iv)
    return cipher.encrypt(pad(bytes.fromhex(HeX), AES.block_size)).hex()

async def DEc_AEs(HeX):
    cipher = AES.new(Key, AES.MODE_CBC, Iv)
    return unpad(cipher.decrypt(bytes.fromhex(HeX)), AES.block_size).hex()

async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def DEc_PacKeT(HeX, K, V):
    return unpad(AES.new(K, AES.MODE_CBC, V).decrypt(bytes.fromhex(HeX)), 16).hex()

async def EnC_Uid(H, Tp):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex() if Tp == 'Uid' else None

async def EnC_Vr(N):
    if N < 0:
        return ''
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)

def DEc_Uid(H):
    n = s = 0
    for b in bytes.fromhex(H):
        n |= (b & 0x7F) << s
        if not b & 0x80:
            break
        s += 7
    return n

async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return await EnC_Vr(field_header) + await EnC_Vr(value)

async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet

async def DecodE_HeX(H):
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        F = "0" + F
        return F
    else:
        return F

async def Fix_PackEt(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type == "varint":
            field_data['data'] = result.data
        if result.wire_type == "string":
            field_data['data'] = result.data
        if result.wire_type == "bytes":
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = await Fix_PackEt(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

async def DeCode_PackEt(input_text):
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_objects = parsed_results
        parsed_results_dict = await Fix_PackEt(parsed_results_objects)
        json_data = json.dumps(parsed_results_dict)
        return json_data
    except Exception as e:
        print(f"error {e}")
        return None

def xMsGFixinG(n):
    return '🗿'.join(str(n)[i:i + 3] for i in range(0, len(str(n)), 3))

async def Ua():
    versions = [
        '4.0.18P6', '4.0.19P7', '4.0.20P1', '4.1.0P3', '4.1.5P2', '4.2.1P8',
        '4.2.3P1', '5.0.1B2', '5.0.2P4', '5.1.0P1', '5.2.0B1', '5.2.5P3',
        '5.3.0B1', '5.3.2P2', '5.4.0P1', '5.4.3B2', '5.5.0P1', '5.5.2P3'
    ]
    models = [
        'SM-A125F', 'SM-A225F', 'SM-A325M', 'SM-A515F', 'SM-A725F', 'SM-M215F', 'SM-M325FV',
        'Redmi 9A', 'Redmi 9C', 'POCO M3', 'POCO M4 Pro', 'RMX2185', 'RMX3085',
        'moto g(9) play', 'CPH2239', 'V2027', 'OnePlus Nord', 'ASUS_Z01QD',
    ]
    android_versions = ['9', '10', '11', '12', '13', '14']
    languages = ['en-US', 'es-MX', 'pt-BR', 'id-ID', 'ru-RU', 'hi-IN']
    countries = ['USA', 'MEX', 'BRA', 'IDN', 'RUS', 'IND']
    version = random.choice(versions)
    model = random.choice(models)
    android = random.choice(android_versions)
    lang = random.choice(languages)
    country = random.choice(countries)
    return f"GarenaMSDK/{version}({model};Android {android};{lang};{country};)"

async def ArA_CoLor():
    Tp = ["32CD32", "00BFFF", "00FA9A", "90EE90", "FF4500", "FF6347", "FF69B4", "FF8C00", "FF6347", "FFD700", "FFDAB9", "F0F0F0", "F0E68C", "D3D3D3", "A9A9A9", "D2691E", "CD853F", "BC8F8F", "6A5ACD", "483D8B", "4682B4", "9370DB", "C71585", "FF8C00", "FFA07A"]
    return random.choice(Tp)

async def xBunnEr():
    bN = [902000126, 902000154, 902000003, 902027018, 902027027, 902039014, 902040027, 902042011, 902048021, 902048018, 902000027, 902000078, 902000013, 902000093, 902000100, 902000117, 902000111, 902000151, 902000207, 902000203, 902027016, 902027018, 902033016, 902027018, 902027018, 902027018, 902027018, 902027018, 902027018]
    return random.choice(bN)

async def xSEndMsg(Msg, Tp, Tp2, id, K, V):
    feilds = {1: id, 2: Tp2, 3: Tp, 4: Msg, 5: 1735129800, 7: 2, 9: {1: "xBesTo - C4", 2: int(await xBunnEr()), 3: 901048018, 4: 330, 5: 909034009, 8: "xBesTo - C4", 10: 1, 11: 1, 13: {1: 2}, 14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}, 12: 0}, 10: "en", 13: {3: 1}}
    Pk = (await CrEaTe_ProTo(feilds)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)

async def xSEndMsgsQ(Msg, id, K, V):
    fields = {1: id, 2: id, 4: Msg, 5: 1756580149, 7: 2, 8: 904990072, 9: {1: "xBe4!sTo - C4", 2: await xBunnEr(), 4: 330, 5: 827001005, 8: "xBe4!sTo - C4", 10: 1, 11: 1, 13: {1: 2}, 14: {1: 1158053040, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0015\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}}, 10: "en", 13: {2: 2, 3: 1}}
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)
    
async def SPamSq(Uid , K , V): 
    fields = {1: 33, 2: {1: int(Uid) , 2: 'ME', 3: 1, 4: 1, 7: 330, 8: 19459, 9: 100, 12: 1, 16: 1, 17: {2: 94, 6: 11, 8: '1.111.5', 9: 3, 10: 2}, 18: 201, 23: {2: 1, 3: 1}, 24: xBunnEr() , 26: {}, 28: {}}}
    return GeneRaTePk(str(CrEaTe_ProTo(fields).hex()) , '0515' , K , V)    

async def ChEck_Commande(id):
    return "<" not in id and ">" not in id and "[" not in id and "]" not in id

async def AuthClan(CLan_Uid, AuTh, K, V):
    fields = {1: 3, 2: {1: int(CLan_Uid), 2: 1, 4: str(AuTh)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1201', K, V)

async def AutH_GlobAl(K, V):
    fields = {
        1: 3,
        2: {
            2: 5,
            3: "en"
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, V)

async def LagSquad(K, V):
    fields = {
        1: 15,
        2: {
            1: 1124759936,
            2: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

async def GeT_Status(PLayer_Uid, K, V):
    PLayer_Uid = await EnC_Uid(PLayer_Uid, Tp='Uid')
    if len(PLayer_Uid) == 8:
        Pk = f'080112080a04{PLayer_Uid}1005'
    elif len(PLayer_Uid) == 10:
        Pk = f"080112090a05{PLayer_Uid}1005"
    return await GeneRaTePk(Pk, '0f15', K, V)

async def SPam_Room(Uid, Rm, Nm, K, V):
    fields = {1: 78, 2: {1: int(Rm), 2: f"[{await ArA_CoLor()}]{Nm}", 3: {2: 1, 3: 1}, 4: 330, 5: 1, 6: 201, 10: await xBunnEr(), 11: int(Uid), 12: 1}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0e15', K, V)

async def GenJoinSquadsPacket(code, K, V):
    fields = {}
    fields[1] = 4
    fields[2] = {}
    fields[2][4] = bytes.fromhex("01090a0b121920")
    fields[2][5] = str(code)
    fields[2][6] = 6
    fields[2][8] = 1
    fields[2][9] = {}
    fields[2][9][2] = 800
    fields[2][9][6] = 11
    fields[2][9][8] = "1.111.1"
    fields[2][9][9] = 5
    fields[2][9][10] = 1
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

async def GenJoinGlobaL(owner, code, K, V):
    fields = {
        1: 4,
        2: {
            1: owner,
            6: 1,
            8: 1,
            13: "en",
            15: code,
            16: "OR",
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

async def FS(K, V):
    fields = {
        1: 9,
        2: {
            1: 13256361202
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

# ==================== [الدوال المعدلة للرقصات] ====================

async def Emote_k(TarGeT, idT, K, V, region):
    """الدالة الرئيسية المعدلة للرقصات - الإصدار المحسن"""
    fields = {
        1: 21,
        2: {
            1: 804266880,  
            2: 909000001,  
            5: {
                1: int(TarGeT),  # ✅ UID الهدف
                3: int(idT),     # ✅ كود الرقصة
            }
        }
    }
    
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    
    print(f"🎭 DEBUG EMOTE_K: Target: {TarGeT}, Emote: {idT}, Region: {region}")
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def spamsq(TarGeT, idT, K, V, region):
    """دالة سبام للسيرفر - محسنة ومتوافقة مع باقي الكود"""
    same_value = random.choice([4096, 16384, 8192])
    
    fields = {
        1: 33,
        2: {
            1: int(TarGeT),  # ✅ استخدام TarGeT بدلاً من idplayer
            2: "ME",
            3: 1,
            4: 1,
            5: bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
            6: f"[C][B][FF0000] @AlliFF_BOT",  # اسم البوت
            7: 330,
            8: 1000,
            10: "ME",
            11: bytes([49, 97, 99, 52, 98, 56, 48, 101, 99, 102, 48, 52, 55, 56,
                      97, 52, 52, 50, 48, 51, 98, 102, 56, 102, 97, 99, 54, 49, 50, 48, 102, 53]),
            12: 1,
            13: int(TarGeT),  # ✅ نفس الهدف
            14: {
                1: 2203434355,
                2: 8,
                3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"
            },
            16: 1,
            17: 1,
            18: 312,
            19: 46,
            23: bytes([16, 1, 24, 1]),
            24: int(await xBunnEr()),  # ✅ استخدام xBunnEr() الموجودة
            26: "",
            28: "",
            31: {
                1: 1,
                2: same_value
            },
            32: same_value,
            34: {
                1: int(TarGeT),  # ✅ نفس الهدف
                2: 8,
                3: bytes([15, 6, 21, 8, 10, 11, 19, 12, 17, 4, 14, 20, 7, 2, 1, 5, 16, 3, 13, 18])
            }
        },
        10: "en",
        13: {
            2: 1,
            3: 1
        }
    }
    
    # تحديد نوع الباكيت حسب المنطقة
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    
    # طباعة معلومات التصحيح
    print(f"📦 SPAMSQ: Target: {TarGeT}, Region: {region}, Packet: {packet}")
    
    # توليد الباكيت وإرجاعه
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)
    

    def send_emote(self, target_id, emote_id):
        """
        Creates and prepares the packet for sending an emote to a target player.
        """



async def SendEmote_v2(target_uid, emote_id, key, iv, region):
    """دالة بديلة للرقصات - إصدار مختلف"""
    fields = {
        1: 45,
        2: {
            1: target_uid,
            2: emote_id,
            3: 1,
            4: int(time.time())
        }
    }
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    
    print(f"🎭 DEBUG SENDEMOTE_V2: Target: {target_uid}, Emote: {emote_id}")
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, key, iv)

async def Emote_Squad(target_uid, emote_id, key, iv, region):
    """دالة للرقصات داخل السكواد - إصدار محسن"""
    fields = {
        1: 21,
        2: {
            1: target_uid,
            2: emote_id,
            3: 2,  # نوع السكواد
            4: 1,
            5: {
                1: target_uid,
                2: emote_id,
                3: 2,
                4: int(time.time())
            },
            6: 1
        }
    }
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    
    print(f"🎭 DEBUG EMOTE_SQUAD: Target: {target_uid}, Emote: {emote_id}")
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, key, iv)

# ==================== [نهاية دوال الرقصات] ====================

async def GeTSQDaTa(D):
    uid = D['5']['data']['1']['data']
    chat_code = D["5"]["data"]["14"]["data"]
    squad_code = D["5"]["data"]["31"]["data"]
    return uid, chat_code, squad_code

async def AutH_Chat(T, uid, code, K, V):
    fields = {
        1: T,
        2: {
            1: uid,
            3: "en",
            4: str(code)
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, V)

def MsqSq(Msg , id , K , V):
    fields = {1: id , 2: id , 4: Msg , 5: 1756580149, 7: 2, 8: 901048018, 9: {1: "MeRoBoT", 2: xBunnEr(), 4: 330, 5: 827001005, 8: "MeRoBoT", 10: 1, 11: 1, 13: {1: 2}, 14: {1: 1158053040, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0015\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}}, 10: "en", 13: {2: 2, 3: 1}}
    Pk = (CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return GeneRaTePk(Pk, '1215', K, V)    

async def ghost_pakcet(player_id , nm , secret_code , key ,iv):
    fields = {
        1: 61,
        2: {
            1: int(player_id),  
            2: {
                1: int(player_id),  
                2: 1159,  
                3: f"[b][c][{await ArA_CoLor()}]{nm}",  # <-- أضف await هنا
                5: 22,  
                6: 20,
                7: 1,
                8: {
                    2: 1,
                    3: 1,
                },
                9: 3,
            },
            3: secret_code,
        }
    }
    # أصلح الاستدعاءات هنا
    proto_bytes = await CrEaTe_ProTo(fields)
    proto_hex = proto_bytes.hex()
    return await GeneRaTePk(proto_hex, '0515', key, iv)  # <-- أضف await هنا
    
async def GeneRaTePk(Pk, N, K, V):
    PkEnc = await EnC_PacKeT(Pk, K, V)
    _ = await DecodE_HeX(int(len(PkEnc) // 2))
    if len(_) == 2:
        HeadEr = N + "000000"
    elif len(_) == 3:
        HeadEr = N + "00000"
    elif len(_) == 4:
        HeadEr = N + "0000"
    elif len(_) == 5:
        HeadEr = N + "000"
    else:
        print('ErroR => GeneRatinG ThE PacKeT !!')
    
    result_packet = bytes.fromhex(HeadEr + _ + PkEnc)
    print(f"📦 DEBUG GENERATEPK: Type: {N}, Length: {len(result_packet)}")
    return result_packet

async def OpEnSq(K, V, region):
    fields = {1: 1, 2: {2: "\u0001", 3: 1, 4: 1, 5: "en", 9: 1, 11: 1, 13: 1, 14: {2: 5756, 6: 11, 8: "1.111.5", 9: 2, 10: 4}}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def cHSq(Nu, Uid, K, V, region):
    fields = {1: 17, 2: {1: int(Uid), 2: 1, 3: int(Nu - 1), 4: 62, 5: "\u001a", 8: 5, 13: 329}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def SEnd_InV(Nu, Uid, K, V, region):
    fields = {1: 2, 2: {1: int(Uid), 2: region, 4: int(Nu)}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def ExiT(idT, K, V):
    fields = {
        1: 7,
        2: {
            1: idT,
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)
    
    
async def ExitTeam(K, V):
    """دالة خروج من الفريق"""
    fields = {
        1: 7,
        2: {
            1: 0,
            2: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)
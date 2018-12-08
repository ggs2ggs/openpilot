# Constants in FlexRay spec
cdCycleMax = 16000
cCycleCountMax = 63
cStaticSlotIDMax = 1023
cSlotIDMax = 2047
cPayloadLengthMax = 127
cSamplesPerBit = 8
cSyncFrameIDCountMax = 15
cMicroPerMacroNomMin = 40
cdMinMTNom = 1
cdMaxMTNom = 6
cdFES = 2
cdFSS = 1
cChannelIdleDelimiter = 11
cClockDeviationMax = 0.0015
cStrobeOffset = 5
cVotingSamples = 5
cVotingDelay = (cVotingSamples - 1) / 2
cdBSS = 2
cdWakeupSymbolTxIdle = 18
cdWakeupSymbolTxLow = 6
cdCAS = 30
cMicroPerMacroMin = 20
cdMaxOffsetCalculation = 1350
cdMaxRateCalculation = 1500

SIZEOF_UINT16 = 2
SIZEOF_PACKET_HEADER = SIZEOF_UINT16 * 2

PACKET_TYPE_START_DRIVER = 0
PACKET_TYPE_FLEXRAY_FRAME = 1
PACKET_TYPE_HEALTH = 2
PACKET_TYPE_FLEXRAY_JOINED_CLUSTER = 3
PACKET_TYPE_FLEXRAY_JOIN_CLUSTER_FAILED = 4
PACKET_TYPE_FLEXRAY_DISCONNECTED_FROM_CLUSTER = 5
PACKET_TYPE_FLEXRAY_FATAL_ERROR = 6

# MPC5748g registers bits
FR_PIFR0_TBVA_IF_U16 = 0x0008
FR_PIFR0_TBVB_IF_U16 = 0x0010
FR_PIFR0_LTXA_IF_U16 = 0x0020
FR_PIFR0_LTXB_IF_U16 = 0x0040
FR_PIER0_CCL_IF_U16 = 0x0200
FR_PIFR0_MOC_IF_U16 = 0x0400
FR_PIFR0_MRC_IF_U16 = 0x0800
FR_PIFR0_INTL_IF_U16 = 0x4000

FR_PIER0_TI2_IE_U16 = 0x0004
FR_PIER0_TI1_IE_U16 = 0x0002

FR_PSR0_ERRMODE_MASK_U16 = 0xC000
FR_PSR0_SLOTMODE_MASK_U16 = 0x3000
FR_PSR0_PROTSTATE_MASK_U16 = 0x0700
FR_PSR0_STARTUP_MASK_U16 = 0x00F0
FR_PSR0_WUP_MASK_U16 = 0x0007
FR_PSR0_SLOTMODE_SINGLE_U16 = 0x0000
FR_PSR0_SLOTMODE_ALL_PENDING_U16 = 0x1000
FR_PSR0_SLOTMODE_ALL_U16 = 0x2000
FR_PSR0_ERRMODE_ACTIVE_U16 = 0x0000
FR_PSR0_ERRMODE_PASSIVE_U16 = 0x4000
FR_PSR0_ERRMODE_COMM_HALT_U16 = 0x8000
FR_PSR0_PROTSTATE_DEFAULT_CONFIG_U16 = 0x0000
FR_PSR0_PROTSTATE_CONFIG_U16 = 0x0100
FR_PSR0_PROTSTATE_WAKEUP_U16 = 0x0200
FR_PSR0_PROTSTATE_READY_U16 = 0x0300
FR_PSR0_PROTSTATE_NORMAL_PASSIVE_U16 = 0x0400
FR_PSR0_PROTSTATE_NORMAL_ACTIVE_U16 = 0x0500
FR_PSR0_PROTSTATE_HALT_U16 = 0x0600
FR_PSR0_PROTSTATE_STARTUP_U16 = 0x0700
FR_PSR0_STARTUP_CCR_U16 = 0x0020
FR_PSR0_STARTUP_CL_U16 = 0x0030
FR_PSR0_STARTUP_ICOC_U16 = 0x0040
FR_PSR0_STARTUP_IL_U16 = 0x0050
FR_PSR0_STARTUP_IS_U16 = 0x0070
FR_PSR0_STARTUP_CCC_U16 = 0x00A0
FR_PSR0_STARTUP_ICLC_U16 = 0x00D0
FR_PSR0_STARTUP_CG_U16 = 0x00E0
FR_PSR0_STARTUP_CJ_U16 = 0x00F0

FR_PSR1_CPN_U16 = 0x0080
FR_PSR1_HHR_U16 = 0x0040
FR_PSR1_FRZ_U16 = 0x0020

FR_PSR2_NBVB_MASK_U16 = 0x8000
FR_PSR2_NSEB_MASK_U16 = 0x4000
FR_PSR2_STCB_MASK_U16 = 0x2000
FR_PSR2_SBVB_MASK_U16 = 0x1000
FR_PSR2_SSEB_MASK_U16 = 0x0800
FR_PSR2_MTB_MASK_U16 = 0x0400
FR_PSR2_NBVA_MASK_U16 = 0x0200
FR_PSR2_NSEA_MASK_U16 = 0x0100
FR_PSR2_STCA_MASK_U16 = 0x0080
FR_PSR2_SBVA_MASK_U16 = 0x0040
FR_PSR2_SSEA_MASK_U16 = 0x0020
FR_PSR2_MTA_MASK_U16 = 0x0010
FR_PSR2_CKCORFCNT_MASK_U16 = 0x000F


FR_PSR3_ABVB_U16 = 0x1000
FR_PSR3_AACB_U16 = 0x0800
FR_PSR3_ACEB_U16 = 0x0400
FR_PSR3_ASEB_U16 = 0x0200
FR_PSR3_AVFB_U16 = 0x0100
FR_PSR3_ABVA_U16 = 0x0010
FR_PSR3_AACA_U16 = 0x0008
FR_PSR3_ACEA_U16 = 0x0004
FR_PSR3_ASEA_U16 = 0x0002
FR_PSR3_AVFA_U16 = 0x0001

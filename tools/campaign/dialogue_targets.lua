-- Natural early-game dialogue records captured by the boundary probe.
--
-- payload_hex contains the exact encoded record, including its $0D
-- terminator, as emitted by script.py.  The Python static test keeps these
-- values synchronized with the translation source.

return {
    {
        source_offset = 0x03082C,
        label = "intro_professor_greeting",
        required = true,
        payload_hex =
            "50524f462e204348454e203a2020202020" ..
            "4269656e206c6520626f6e6a6f757220212020" ..
            "4269656e76656e756520212020202020202020" ..
            "566f696369206c65206d6f6e64652020202020" ..
            "64657320506f6b406d6f6e2021202020202020" ..
            "4d6f692c206327657374204368656e2c202020" ..
            "6c652050726f6620506f6b406d6f6e20212020" ..
            "49636920766976656e74202020202020202020" ..
            "64657320637240617475726573202020202020" ..
            "617070656c40657320506f6b406d6f6e20210d",
    },
    {
        source_offset = 0x035DCC,
        label = "intro_pokemon_world",
        required = true,
        payload_hex =
            "4365206d6f6e6465206162726974652020" ..
            "64657320637240617475726573202020202020" ..
            "617070656c40657320506f6b406d6f6e202120" ..
            "4365727461696e7320656e20666f6e74202020" ..
            "64657320636f6d7061676e6f6e732e20202020" ..
            "4427617574726573206c657320666f6e742020" ..
            "636f6d6261747472652e202020202020202020" ..
            "4d6f692c206a65206c6573204074756469652e0d",
    },
    {
        source_offset = 0x035E82,
        label = "intro_legend_begins",
        required = true,
        payload_hex =
            "5341434841202120202020202020202020" ..
            "54612071757d746520506f6b406d6f6e202020" ..
            "766120636f6d6d656e63657220212020202020" ..
            "556e206d6f6e646520646520727d7665732020" ..
            "65742064276176656e74757265732020202020" ..
            "7427617474656e6420210d",
    },
    {
        source_offset = 0x03F27B,
        label = "pallet_mother_downstairs",
        required = true,
        milestone = "mother_downstairs",
        payload_hex =
            "4d414d414e203a20432765737420767261692e" ..
            "546f7573206c6573206761725b6f6e73202020" ..
            "70617274656e7420756e206a6f75722e202020" ..
            "4c612074406c40206c27612064697420212020" ..
            "4c652050726f6620746520636865726368652e" ..
            "496c20657374207b20635e74402e0d",
    },
    {
        source_offset = 0x038519,
        label = "pallet_oak_warning",
        required = true,
        milestone = "oak_first_meeting",
        payload_hex =
            "50524f462e204348454e203a20202020202020" ..
            "4e6520736f7273207061732021202020202020" ..
            "44657320506f6b406d6f6e20725e64656e7420" ..
            "64616e73206c6573206865726265732e202020" ..
            "496c207427656e206661757420756e2e202020" ..
            "537569732d6d6f6920210d",
    },
    {
        source_offset = 0x03F2EE,
        label = "oak_lab_initial_speech",
        required = true,
        milestone = "oak_lab_initial",
        payload_hex =
            "50524f462e204348454e203a20202020202020" ..
            "5240676973203f2044406a7b206c7b203f2020" ..
            "4a652074276176616973206469742020202020" ..
            "6427617474656e6472652e2053616368612c20" ..
            "636574746520506f6b402042616c6c20202020" ..
            "636f6e7469656e742020202020202020202020" ..
            "746f6e20506f6b406d6f6e2e20202020202020" ..
            "5072656e64732d6c6120210d",
    },
    {
        source_offset = 0x034CB3,
        label = "pallet_technology_npc",
        required = false,
        milestone = "pallet_optional",
        payload_hex =
            "4d6f692061757373692c206a27406c7c766520" ..
            "64657320506f6b406d6f6e20666f7274732e20" ..
            "46696e69206c6573206272696d6164657320210d",
    },
    {
        source_offset = 0x034D08,
        label = "route1_ledge_npc",
        required = false,
        milestone = "route1",
        payload_hex =
            "506f6b402042616c6c7320656e2076656e7465" ..
            "7b206c6120426f75746971756520210d",
    },
    {
        source_offset = 0x034D3A,
        label = "route1_sign",
        required = false,
        milestone = "route1",
        payload_hex =
            "556e20506f6b406d6f6e2063686f7940202020" ..
            "7327617474616368657261207b20746f692e0d",
    },
    {
        source_offset = 0x034D4C,
        label = "route1_mart_employee",
        required = false,
        milestone = "route1",
        payload_hex =
            "566f6c6572206661697420706575722c202020" ..
            "6d6169732074652072616d7c6e652076697465" ..
            "7b20426f7572672050616c657474652e0d",
    },
    {
        source_offset = 0x034DE5,
        label = "viridian_gym_closed",
        required = false,
        milestone = "jadielle",
        payload_hex =
            "43657474652041727c6e6520506f6b406d6f6e" ..
            "7265737465206665726d40652e202020202020" ..
            "5175692065737420646f6e6320202020202020" ..
            "6c65204368616d70696f6e203f0d",
    },
    {
        source_offset = 0x0387F3,
        label = "viridian_mart_oak_parcel",
        required = false,
        milestone = "jadielle",
        payload_hex =
            "426f7572672050616c65747465203f20202020" ..
            "506f727465206c6120636f6d6d616e64652020" ..
            "64752050726f662e204368656e20210d",
    },
}

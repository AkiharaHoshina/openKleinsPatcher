# 老客户端改动 → 跨版本可移植性分类

| 类别 | 数量 | 含义 |
|---|---|---|
| ① SAME_S | 7 | 改成了 Steam 原版 —— **不是补丁** |
| ② ONE_HASH | 75 | 两版原版相同 —— 一条哈希可同时适配 |
| ③ TWO_HASH | 10 | 两版原版不同 —— 需按版本分条 |
| ? GONE | 0 | Steam 里没这个文件 |

## ① SAME_S —— 其实是 Steam 的文件，别当补丁

| 文件 | 代 | 老版原版 | 补丁后 == Steam |
|---|---|---|---|
| `Win/lua/logic/emotion_shop_ui/logic_emotion_shop.lua` | 1 | 485 B | `9b22c7426b33` |
| `Win/lua/logic/event_emotion/logic_event_emotion.lua` | 1 | 9784 B | `0e242953e379` |
| `Win/lua/logic/event_emotion/view_event_emotion_home_ui.lua` | 1 | 14468 B | `0959605f043b` |
| `Win/lua/logic/event_emotion/view_event_emotion_level_detail_ui.lua` | 1 | 8808 B | `83031fd06238` |
| `Win/lua/logic/event_emotion/view_event_emotion_level_list_ui.lua` | 1 | 13076 B | `203a7c05b5d9` |
| `Win/lua/logic/event_emotion/view_event_emotion_task_ui.lua` | 1 | 9457 B | `f7726a62cdc0` |
| `Win/lua/logic/recruit_ui/view_recruit_free_ui.lua` | 1 | 21790 B | `2c3fb483f007` |

## ? GONE —— Steam 里不存在（补丁对 Steam 无意义）

| 文件 | 代 | 老版原版 sha | Steam 原版 sha | 老版大小 | Steam 大小 |
|---|---|---|---|---|---|

## ③ TWO_HASH —— 两版原版不同，清单需按版本分条

| 文件 | 代 | 老版原版 sha | Steam 原版 sha | 老版大小 | Steam 大小 |
|---|---|---|---|---|---|
| `GameAssembly.dll` | 1 | `ab8cee74ea61` | `c875a76e7fe4` | 47348872 | 47953920 |
| `Win/lua/logic/anti_addiction/logic_anti_addiction.lua` | 1 | `007a42ea376e` | `1cd9bd60e141` | 8884 | 8860 |
| `Win/lua/logic/emotion_shop_ui/view_emotion_shop_ui.lua` | 1 | `a3a58b8b906c` | `aa8a9cfc457e` | 8428 | 8428 |
| `Win/lua/logic/event_emotion/view_event_emotion_memory_analysis_ui.lua` | 1 | `198888d2a060` | `a93aded9c732` | 13322 | 13288 |
| `Win/lua/logic/framework/lua_data_center.lua` | 1 | `5480a15fdde8` | `82bb23f44783` | 8587 | 8553 |
| `Win/lua/logic/login_ui/view_game_main_ui.lua` | 2 | `653c9bd4efd3` | `32788f732450` | 8811 | 8791 |
| `Win/lua/logic/setting_ui/view_setting_account_ui.lua` | 1 | `64675dd938af` | `54bf645c6141` | 9967 | 9867 |
| `Win/lua/sdk/sdk_ios.lua` | 1 | `2686740575f2` | `753eb35b1fcf` | 7326 | 6970 |
| `userprofile.bin` | 1 | `383df4413e70` | `70e6c66356e1` | 9440 | 64 |
| `环行旅舍_Data/resources.assets` | 1 | `129cedea7f7c` | `5ecb69edb6ba` | 1100624 | 1100624 |

## ② ONE_HASH —— 两版原版相同（最理想）

| 文件 | 代 | 老版原版 sha | Steam 原版 sha | 老版大小 | Steam 大小 |
|---|---|---|---|---|---|
| `Win/lua/common/Utils.lua` | 1 | `2db1b9cc0c55` | `2db1b9cc0c55` | 22948 | 22948 |
| `Win/lua/logic/active_box_ui/active_box_config.lua` | 1 | `faa5d9594b95` | `faa5d9594b95` | 731 | 731 |
| `Win/lua/logic/active_box_ui/box_child/view_active_charge.lua` | 1 | `77d2be4d00f3` | `77d2be4d00f3` | 5660 | 5660 |
| `Win/lua/logic/active_box_ui/logic_active_box.lua` | 1 | `25c4e874e628` | `25c4e874e628` | 3354 | 3354 |
| `Win/lua/logic/active_box_ui/logic_box/logic_box_charge.lua` | 1 | `aa929c004a0e` | `aa929c004a0e` | 2988 | 2988 |
| `Win/lua/logic/activity_time/logic_activity_time.lua` | 1 | `3384448db7cb` | `3384448db7cb` | 6373 | 6373 |
| `Win/lua/logic/audio/audio_config.lua` | 1 | `ac2e35d262a4` | `ac2e35d262a4` | 17301 | 17301 |
| `Win/lua/logic/battle_ui/view_battle_win_ui.lua` | 1 | `2e175b3db7f5` | `2e175b3db7f5` | 11170 | 11170 |
| `Win/lua/logic/chapter_ui/logic_chapter.lua` | 1 | `dd46546fcd8d` | `dd46546fcd8d` | 21451 | 21451 |
| `Win/lua/logic/chapter_ui/view_level_detail_ui.lua` | 1 | `72040895cf97` | `72040895cf97` | 8107 | 8107 |
| `Win/lua/logic/chapter_ui/view_level_sweep_result_ui.lua` | 1 | `3fb34bfee64d` | `3fb34bfee64d` | 9538 | 9538 |
| `Win/lua/logic/chapter_ui/view_stop_sweep_ui.lua` | 1 | `86651ceade06` | `86651ceade06` | 2855 | 2855 |
| `Win/lua/logic/common/common_config.lua` | 1 | `c114b2965fd3` | `c114b2965fd3` | 5103 | 5103 |
| `Win/lua/logic/common/config_data_center.lua` | 2 | `3b01443c9aca` | `3b01443c9aca` | 8982 | 8982 |
| `Win/lua/logic/common/enter_necessary_infos.lua` | 1 | `3a489fad4287` | `3a489fad4287` | 2041 | 2041 |
| `Win/lua/logic/common/red_point_mgr.lua` | 1 | `8d16b6dbfb09` | `8d16b6dbfb09` | 8522 | 8522 |
| `Win/lua/logic/common/ui_config.lua` | 1 | `c7dd1fbcf6c3` | `c7dd1fbcf6c3` | 32769 | 32769 |
| `Win/lua/logic/common/uimgr.lua` | 2 | `bea4932d4af6` | `bea4932d4af6` | 11253 | 11253 |
| `Win/lua/logic/endless_ui/view_endless_clear_ui.lua` | 1 | `45ec8fe46f44` | `45ec8fe46f44` | 7756 | 7756 |
| `Win/lua/logic/first_recharge_act/logic_first_recharge_act.lua` | 1 | `0f8f9a5c98c8` | `0f8f9a5c98c8` | 3316 | 3316 |
| `Win/lua/logic/framework/cmdName.lua` | 1 | `a91d34763ee9` | `a91d34763ee9` | 6275 | 6275 |
| `Win/lua/logic/framework/net_error_handler.lua` | 2 | `0afff950a4f4` | `0afff950a4f4` | 10559 | 10559 |
| `Win/lua/logic/guide/guide_mgr.lua` | 1 | `21e46d740f24` | `21e46d740f24` | 10678 | 10678 |
| `Win/lua/logic/home_cultivate/home_ui_service.lua` | 1 | `b161a3729b56` | `b161a3729b56` | 4008 | 4008 |
| `Win/lua/logic/home_ui/logic_home.lua` | 1 | `53a687b9b18c` | `53a687b9b18c` | 6787 | 6787 |
| `Win/lua/logic/home_ui/view_home_ui.lua` | 2 | `4d13ae72e440` | `4d13ae72e440` | 42842 | 42842 |
| `Win/lua/logic/language/language_config.lua` | 1 | `1e0a9cb2509d` | `1e0a9cb2509d` | 28107 | 28107 |
| `Win/lua/logic/login_ui/logic_login_main.lua` | 2 | `488f0aacd81b` | `488f0aacd81b` | 11703 | 11703 |
| `Win/lua/logic/login_ui/view_login_ui.lua` | 2 | `47159d31072f` | `47159d31072f` | 10622 | 10622 |
| `Win/lua/logic/mail_ui/logic_mail.lua` | 2 | `b8ebeb3b800d` | `b8ebeb3b800d` | 5721 | 5721 |
| `Win/lua/logic/notice_ui/view_normal_notice_ui.lua` | 2 | `048e6135b55a` | `048e6135b55a` | 10783 | 10783 |
| `Win/lua/logic/private_message/logic_private_message.lua` | 1 | `e1608ce5ef45` | `e1608ce5ef45` | 14310 | 14310 |
| `Win/lua/logic/private_message/view_private_message_ui.lua` | 1 | `851bb67740b4` | `851bb67740b4` | 23934 | 23934 |
| `Win/lua/logic/recruit_pay_ui/logic_recruit_pay.lua` | 1 | `4663284be79f` | `4663284be79f` | 8601 | 8601 |
| `Win/lua/logic/recruit_pay_ui/view_multi_recruit_ui.lua` | 1 | `ffdb0cf2aba7` | `ffdb0cf2aba7` | 5875 | 5875 |
| `Win/lua/logic/recruit_pay_ui/view_recruit_history_ui.lua` | 1 | `cee0e8daa13b` | `cee0e8daa13b` | 4019 | 4019 |
| `Win/lua/logic/recruit_pay_ui/view_recruit_pay_ui.lua` | 2 | `0276cee872a2` | `0276cee872a2` | 14626 | 14626 |
| `Win/lua/logic/recruit_pay_ui/view_recruit_share_ui.lua` | 2 | `8a625c7c8784` | `8a625c7c8784` | 3607 | 3607 |
| `Win/lua/logic/recruit_pay_ui/view_single_recruit_ui.lua` | 1 | `367267c90b8d` | `367267c90b8d` | 11272 | 11272 |
| `Win/lua/logic/role_info_ui/logic_role.lua` | 2 | `5aa410288f4a` | `5aa410288f4a` | 11605 | 11605 |
| `Win/lua/logic/role_info_ui/logic_role_data.lua` | 2 | `cad7273bada1` | `cad7273bada1` | 31728 | 31728 |
| `Win/lua/logic/role_post/logic_change_scene.lua` | 2 | `b50d19a1e211` | `b50d19a1e211` | 2585 | 2585 |
| `Win/lua/logic/role_queue/view_queue_normal_ui.lua` | 1 | `ddc4f33e768a` | `ddc4f33e768a` | 12203 | 12203 |
| `Win/lua/logic/role_queue/view_role_queue_base.lua` | 2 | `8664dd4a1289` | `8664dd4a1289` | 5281 | 5281 |
| `Win/lua/logic/role_ui/model_role_data.lua` | 1 | `996fc2ea522a` | `996fc2ea522a` | 6187 | 6187 |
| `Win/lua/logic/role_ui/role_develop_ui/view_role_details_ui.lua` | 1 | `68c12185e9d7` | `68c12185e9d7` | 15431 | 15431 |
| `Win/lua/logic/role_ui/role_develop_ui/view_role_dna_ui.lua` | 1 | `b9bfccb723cb` | `b9bfccb723cb` | 3121 | 3121 |
| `Win/lua/logic/role_ui/role_develop_ui/view_role_rank_ui.lua` | 1 | `5b4a109c9c8f` | `5b4a109c9c8f` | 12184 | 12184 |
| `Win/lua/logic/role_ui/role_skin_ui/logic_role_skin.lua` | 2 | `f30141039d71` | `f30141039d71` | 4518 | 4518 |
| `Win/lua/logic/role_ui/role_skin_ui/view_role_skin_base.lua` | 2 | `b0f51a90a58f` | `b0f51a90a58f` | 10621 | 10621 |
| `Win/lua/logic/scene_state/battle_scene.lua` | 1 | `cd91eeff71d0` | `cd91eeff71d0` | 6687 | 6687 |
| `Win/lua/logic/scene_state/home_scene.lua` | 2 | `50f7e811952f` | `50f7e811952f` | 1621 | 1621 |
| `Win/lua/logic/select_role_ui/select_role/view_role_select_base.lua` | 2 | `7cf88a4630ae` | `7cf88a4630ae` | 36432 | 36432 |
| `Win/lua/logic/setting_ui/view_setting_ui.lua` | 2 | `216c5806fc75` | `216c5806fc75` | 3500 | 3500 |
| `Win/lua/logic/shop_ui/logic_shop.lua` | 2 | `cf8cb9f4ddc8` | `cf8cb9f4ddc8` | 16062 | 16062 |
| `Win/lua/logic/shop_ui/sub_shop/view_shop_gift_ui.lua` | 2 | `05dd86f5484a` | `05dd86f5484a` | 4035 | 4035 |
| `Win/lua/logic/shop_ui/sub_shop/view_shop_heterochromatic_ui.lua` | 2 | `1eced6b2a44a` | `1eced6b2a44a` | 4185 | 4185 |
| `Win/lua/logic/shop_ui/sub_shop/view_shop_today_ui.lua` | 2 | `b9607c5258d0` | `b9607c5258d0` | 6198 | 6198 |
| `Win/lua/logic/shop_ui/view_pop_buy_item_ui.lua` | 2 | `6fb6656280ee` | `6fb6656280ee` | 11069 | 11069 |
| `Win/lua/logic/shop_ui/view_pop_buy_month_card_ui.lua` | 2 | `e01a7137a41c` | `e01a7137a41c` | 7434 | 7434 |
| `Win/lua/logic/shop_ui/view_shopping_center_ui.lua` | 2 | `c6fde43fee4f` | `c6fde43fee4f` | 12424 | 12424 |
| `Win/lua/logic/tactic_review_ui/view_tactic_review_result.lua` | 1 | `2e41f951a463` | `2e41f951a463` | 3413 | 3413 |
| `Win/lua/logic/task_ui/logic_task_main.lua` | 2 | `f36d569a98b4` | `f36d569a98b4` | 11253 | 11253 |
| `Win/lua/logic/turn_activity/controller_turn_activity.lua` | 1 | `119d02f860af` | `119d02f860af` | 9983 | 9983 |
| `Win/lua/logic/turn_activity/logic_page/logic_battle_page.lua` | 1 | `36ee237680c5` | `36ee237680c5` | 15284 | 15284 |
| `Win/lua/logic/turn_activity/logic_page/logic_home_page.lua` | 1 | `856e479cd178` | `856e479cd178` | 9153 | 9153 |
| `Win/lua/logic/turn_activity/model_turn_activity_data.lua` | 1 | `ca0f65098798` | `ca0f65098798` | 16573 | 16573 |
| `Win/lua/logic/turn_activity/turn_act_config.lua` | 1 | `4c1f285bf9b4` | `4c1f285bf9b4` | 569 | 569 |
| `Win/lua/protobuf_conf_parser/config.lua` | 1 | `9bd414157b10` | `9bd414157b10` | 54179 | 54179 |
| `Win/lua/protocol_generated/cs_cmdvalue_pb.lua` | 1 | `63783519d2d8` | `63783519d2d8` | 55735 | 55735 |
| `Win/lua/protocol_generated/cs_login_pb.lua` | 1 | `f20a0f057319` | `f20a0f057319` | 18147 | 18147 |
| `Win/lua/protocol_generated/cs_recruit_pb.lua` | 1 | `50bea02041da` | `50bea02041da` | 19764 | 19764 |
| `Win/lua/sdk/sdk_mgr.lua` | 1 | `f88162e23cea` | `f88162e23cea` | 6481 | 6481 |
| `Win/lua/sdk/sdk_quick.lua` | 1 | `17230554c0e9` | `17230554c0e9` | 3554 | 3554 |
| `Win/lua/sdk/sdk_steam.lua` | 1 | `b0b88f7f0b62` | `b0b88f7f0b62` | 3113 | 3113 |

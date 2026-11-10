import json
def nc(name, cl, tw, vd, vh, prio):
    return {"name":name,"clearance":cl,"track_width":tw,"via_diameter":vd,"via_drill":vh,"microvia_diameter":0.3,"microvia_drill":0.1,
            "diff_pair_width":0.2,"diff_pair_gap":0.15,"diff_pair_via_gap":0.25,"bus_width":12,"wire_width":6,"line_style":0,
            "pcb_color":"rgba(0, 0, 0, 0.000)","schematic_color":"rgba(0, 0, 0, 0.000)","priority":prio,"tuning_profile":""}
power=["+3V3","+BATT","VBUS","/VSYS","/VPERIPH","GND"]
pro={"meta":{"filename":"esp32c6-sht4x.kicad_pro","version":3},
 "board":{"design_settings":{"rules":{"min_copper_edge_clearance":0.3,"min_hole_clearance":0.15,"min_clearance":0.1,"min_track_width":0.127,"min_via_diameter":0.45,"min_through_hole_diameter":0.3,"min_via_annular_width":0.1,"min_hole_to_hole":0.25,"min_silk_clearance":0.0,"min_text_height":0.3,"min_text_thickness":0.05,"solder_mask_to_copper_clearance":0.0,"min_connection":0.0,"min_microvia_diameter":0.2,"min_microvia_drill":0.1,"min_resolved_spokes":1,"use_height_for_length_calcs":True}}},
 "net_settings":{"classes":[nc("Default",0.15,0.15,0.5,0.3,2147483647),nc("Power",0.15,0.25,0.5,0.3,0),nc("RF",0.2,0.35,0.5,0.3,1)],
   "meta":{"version":5},"net_colors":None,"netclass_assignments":None,
   "netclass_patterns":[{"netclass":"Power","pattern":p} for p in power]+[{"netclass":"RF","pattern":"Net-(U1-ANT)"},{"netclass":"RF","pattern":"Net-(AE1-FEED)"}]}}
json.dump(pro,open('proj/esp32c6-sht4x.kicad_pro','w'),indent=2)

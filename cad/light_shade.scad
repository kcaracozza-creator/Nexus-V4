// ============================================================
// NEXUS Scanner Station - Light Shade / Canopy (Parametric)
// All dimensions in mm. Change any parameter below.
// ============================================================

/* [Base - Bottom Opening] */
base_length = 260;        // mm - bottom opening length (X)
base_width  = 220;        // mm - bottom opening width (Y)

/* [Top - Upper Opening] */
top_length = 160;         // mm - top panel length (X)
top_width  = 130;         // mm - top panel width (Y)

/* [Overall] */
shade_height    = 120;    // mm - total height of shade
wall_thickness  = 2.0;    // mm - wall/panel thickness
lip_height      = 8;      // mm - bottom lip that sits on the lightbox
lip_inset       = 2;      // mm - how far lip goes inward

/* [Top Panel] */
top_panel       = true;   // include solid top panel
vent_slot_width = 3;      // mm - vent gap between roof and top panel

/* [Side Heatsinks] */
// Rectangular cutouts on side walls for heatsink fins / ventilation
heatsink_enabled = true;  // enable side heatsink cutouts
heatsink_width   = 60;    // mm - cutout width along wall
heatsink_height  = 40;    // mm - cutout height
heatsink_z       = 60;    // mm - center height from bottom of shade
// Which sides get heatsink cutouts (front/back = Y walls, left/right = X walls)
heatsink_front   = true;
heatsink_back    = true;
heatsink_left    = false;
heatsink_right   = false;
// Heatsink fin grille
heatsink_fins    = true;  // add horizontal fin louvers in cutout
heatsink_fin_count = 5;   // number of horizontal fins
heatsink_fin_thick = 1.5; // mm - fin thickness

/* [LED Ring Channels] */
// Channel = circular groove cut into inner ceiling for ring to press-fit
// Set ring_X_enabled = false to skip any channel
channel_depth   = 3;      // mm - how deep the groove is
channel_width   = 12;     // mm - width of groove (fits LED strip)

// CH1: 12 LED ring
ring_1_enabled  = true;
ring_1_dia      = 37;     // mm - outer diameter of ring
ring_1_x        = 0;      // mm - X offset from center
ring_1_y        = 0;      // mm - Y offset from center
ring_1_z        = 0;      // mm - Z offset from ceiling (0=flush)

// CH2: 8 LED ring
ring_2_enabled  = true;
ring_2_dia      = 32;
ring_2_x        = -50;
ring_2_y        = 0;
ring_2_z        = 0;

// CH3: 1 LED (case light - always on)
ring_3_enabled  = true;
ring_3_dia      = 10;     // single LED, small mount
ring_3_x        = 50;
ring_3_y        = 0;
ring_3_z        = 0;

// CH4: 24 LED ring
ring_4_enabled  = true;
ring_4_dia      = 66;
ring_4_x        = 0;
ring_4_y        = 45;
ring_4_z        = 0;

// CH5: 16 LED ring
ring_5_enabled  = true;
ring_5_dia      = 44;
ring_5_x        = -50;
ring_5_y        = 45;
ring_5_z        = 0;

// CH6: 16 LED ring
ring_6_enabled  = true;
ring_6_dia      = 44;
ring_6_x        = 50;
ring_6_y        = 45;
ring_6_z        = 0;

// CH7: 24 LED ring
ring_7_enabled  = true;
ring_7_dia      = 66;
ring_7_x        = 0;
ring_7_y        = -45;
ring_7_z        = 0;

// CH8: 32 LED ring
ring_8_enabled  = true;
ring_8_dia      = 86;
ring_8_x        = 0;
ring_8_y        = -45;
ring_8_z        = 20;     // lower down from ceiling

// Wire routing
wire_channel     = true;  // cut wire channels between rings
wire_channel_w   = 5;     // mm - wire channel width
wire_channel_d   = 2;     // mm - wire channel depth

/* [Baffles / Internal Grid] */
baffles         = true;   // include internal egg-crate baffles
baffle_rows     = 4;      // number of baffles along length (X)
baffle_cols     = 3;      // number of baffles along width (Y)
baffle_depth    = 50;     // mm - how far baffles hang down from top
baffle_thickness = 1.2;   // mm - baffle wall thickness

/* [Faceted Surface] */
faceted         = true;   // add triangular facet pattern to outer walls
facet_rows      = 2;      // rows of diamond facets per side panel
facet_depth     = 5;      // mm - how far facets protrude outward

/* [Mounting] */
mount_tabs      = true;   // add mounting tabs at bottom corners
tab_width       = 15;     // mm
tab_length      = 20;     // mm
tab_hole_dia    = 4;      // mm - screw hole diameter

// ============================================================
// COMPUTED VALUES
// ============================================================
$fn = 60;

base_x = base_length;
base_y = base_width;
top_x  = top_length;
top_y  = top_width;

taper_x = (base_x - top_x) / 2;
taper_y = (base_y - top_y) / 2;

// Ceiling Z position (inside surface of top)
ceiling_z = shade_height - wall_thickness;

// ============================================================
// MODULES
// ============================================================

// Truncated pyramid (frustum) - solid
module frustum(bx, by, tx, ty, h) {
    hull() {
        translate([0, 0, 0])
            cube([bx, by, 0.01], center=true);
        translate([0, 0, h])
            cube([tx, ty, 0.01], center=true);
    }
}

// Hollow frustum shell
module shade_shell() {
    difference() {
        frustum(base_x, base_y, top_x, top_y, shade_height);

        translate([0, 0, -0.1])
            frustum(
                base_x - wall_thickness*2,
                base_y - wall_thickness*2,
                top_x  - wall_thickness*2,
                top_y  - wall_thickness*2,
                shade_height + 0.2
            );
    }
}

// Bottom lip
module bottom_lip() {
    difference() {
        translate([0, 0, -lip_height])
            cube([base_x + lip_inset*2, base_y + lip_inset*2, lip_height], center=true);

        translate([0, 0, -lip_height - 0.1])
            cube([base_x - wall_thickness*2, base_y - wall_thickness*2, lip_height + 0.2], center=true);
    }
}

// Top panel (solid - no heatsink hole, heatsinks are on the sides)
module top_panel() {
    if (top_panel) {
        translate([0, 0, shade_height + vent_slot_width]) {
            cube([top_x, top_y, wall_thickness], center=true);
        }
    }
}

// Side heatsink cutout (single rectangular opening with optional fin grille)
module heatsink_cutout(wall_w, wall_h) {
    if (heatsink_fins) {
        // Cut the full rectangle, then we'll add fins back
        cube([heatsink_width, wall_thickness + 2, heatsink_height], center=true);
    } else {
        cube([heatsink_width, wall_thickness + 2, heatsink_height], center=true);
    }
}

// Fin grille insert (added back into the cutout)
module heatsink_fin_grille() {
    if (heatsink_fins) {
        fin_spacing = heatsink_height / (heatsink_fin_count + 1);
        for (i = [1:heatsink_fin_count]) {
            z_off = -heatsink_height/2 + i * fin_spacing;
            translate([0, 0, z_off])
                cube([heatsink_width - 2, wall_thickness, heatsink_fin_thick], center=true);
        }
    }
}

// All side heatsink cutouts (subtracted from shell)
module side_heatsink_cuts() {
    if (heatsink_enabled) {
        // Interpolate wall position at heatsink_z height
        // The frustum tapers, so wall X/Y position depends on Z
        frac = heatsink_z / shade_height;
        wall_x_at_z = base_x + (top_x - base_x) * frac;
        wall_y_at_z = base_y + (top_y - base_y) * frac;

        // Front wall (−Y face)
        if (heatsink_front)
            translate([0, -wall_y_at_z/2, heatsink_z])
                rotate([90, 0, 0])
                    heatsink_cutout(wall_x_at_z, shade_height);

        // Back wall (+Y face)
        if (heatsink_back)
            translate([0, wall_y_at_z/2, heatsink_z])
                rotate([90, 0, 0])
                    heatsink_cutout(wall_x_at_z, shade_height);

        // Left wall (−X face)
        if (heatsink_left)
            translate([-wall_x_at_z/2, 0, heatsink_z])
                rotate([0, 90, 0])
                    rotate([0, 0, 90])
                        heatsink_cutout(wall_y_at_z, shade_height);

        // Right wall (+X face)
        if (heatsink_right)
            translate([wall_x_at_z/2, 0, heatsink_z])
                rotate([0, 90, 0])
                    rotate([0, 0, 90])
                        heatsink_cutout(wall_y_at_z, shade_height);
    }
}

// Fin grilles (added back as solid geometry)
module side_heatsink_fins() {
    if (heatsink_enabled && heatsink_fins) {
        frac = heatsink_z / shade_height;
        wall_x_at_z = base_x + (top_x - base_x) * frac;
        wall_y_at_z = base_y + (top_y - base_y) * frac;

        if (heatsink_front)
            translate([0, -wall_y_at_z/2, heatsink_z])
                rotate([90, 0, 0])
                    heatsink_fin_grille();

        if (heatsink_back)
            translate([0, wall_y_at_z/2, heatsink_z])
                rotate([90, 0, 0])
                    heatsink_fin_grille();

        if (heatsink_left)
            translate([-wall_x_at_z/2, 0, heatsink_z])
                rotate([0, 90, 0])
                    rotate([0, 0, 90])
                        heatsink_fin_grille();

        if (heatsink_right)
            translate([wall_x_at_z/2, 0, heatsink_z])
                rotate([0, 90, 0])
                    rotate([0, 0, 90])
                        heatsink_fin_grille();
    }
}

// Single ring channel groove (cut into ceiling)
module ring_channel(dia, cx, cy, cz) {
    translate([cx, cy, ceiling_z - cz]) {
        difference() {
            cylinder(d=dia + channel_width, h=channel_depth + 0.1);
            translate([0, 0, -0.05])
                cylinder(d=dia - channel_width, h=channel_depth + 0.2);
        }
    }
}

// All LED ring channels (subtracted from shell)
module all_ring_channels() {
    if (ring_1_enabled) ring_channel(ring_1_dia, ring_1_x, ring_1_y, ring_1_z);
    if (ring_2_enabled) ring_channel(ring_2_dia, ring_2_x, ring_2_y, ring_2_z);
    if (ring_3_enabled) ring_channel(ring_3_dia, ring_3_x, ring_3_y, ring_3_z);
    if (ring_4_enabled) ring_channel(ring_4_dia, ring_4_x, ring_4_y, ring_4_z);
    if (ring_5_enabled) ring_channel(ring_5_dia, ring_5_x, ring_5_y, ring_5_z);
    if (ring_6_enabled) ring_channel(ring_6_dia, ring_6_x, ring_6_y, ring_6_z);
    if (ring_7_enabled) ring_channel(ring_7_dia, ring_7_x, ring_7_y, ring_7_z);
    if (ring_8_enabled) ring_channel(ring_8_dia, ring_8_x, ring_8_y, ring_8_z);
}

// Ring position markers (visual only, for preview)
module ring_preview(dia, cx, cy, cz) {
    color("blue", 0.5)
    translate([cx, cy, ceiling_z - cz - 1]) {
        difference() {
            cylinder(d=dia, h=2);
            translate([0, 0, -0.1])
                cylinder(d=dia - 8, h=2.2);
        }
    }
}

module all_ring_previews() {
    if (ring_1_enabled) ring_preview(ring_1_dia, ring_1_x, ring_1_y, ring_1_z);
    if (ring_2_enabled) ring_preview(ring_2_dia, ring_2_x, ring_2_y, ring_2_z);
    if (ring_3_enabled) ring_preview(ring_3_dia, ring_3_x, ring_3_y, ring_3_z);
    if (ring_4_enabled) ring_preview(ring_4_dia, ring_4_x, ring_4_y, ring_4_z);
    if (ring_5_enabled) ring_preview(ring_5_dia, ring_5_x, ring_5_y, ring_5_z);
    if (ring_6_enabled) ring_preview(ring_6_dia, ring_6_x, ring_6_y, ring_6_z);
    if (ring_7_enabled) ring_preview(ring_7_dia, ring_7_x, ring_7_y, ring_7_z);
    if (ring_8_enabled) ring_preview(ring_8_dia, ring_8_x, ring_8_y, ring_8_z);
}

// Wire routing channels between rings
module wire_channels() {
    if (wire_channel) {
        // Main wire trunk running along Y axis at ceiling
        translate([-wire_channel_w/2, -top_y/2 + 10, ceiling_z])
            cube([wire_channel_w, top_y - 20, wire_channel_d]);

        // Cross channel running along X axis
        translate([-top_x/2 + 10, -wire_channel_w/2, ceiling_z])
            cube([top_x - 20, wire_channel_w, wire_channel_d]);
    }
}

// Egg-crate baffle grid
module baffles() {
    if (baffles) {
        inner_x = top_x - wall_thickness*2;
        inner_y = top_y - wall_thickness*2;
        spacing_x = inner_x / (baffle_rows + 1);
        spacing_y = inner_y / (baffle_cols + 1);

        translate([0, 0, shade_height - baffle_depth/2]) {
            for (i = [1:baffle_rows]) {
                x_pos = -inner_x/2 + i * spacing_x;
                translate([x_pos, 0, 0])
                    baffle_plane(baffle_thickness, inner_y, baffle_depth);
            }
            for (j = [1:baffle_cols]) {
                y_pos = -inner_y/2 + j * spacing_y;
                translate([0, y_pos, 0])
                    rotate([0, 0, 90])
                        baffle_plane(baffle_thickness, inner_x, baffle_depth);
            }
        }
    }
}

module baffle_plane(length, height, thickness) {
    cube([length, thickness, height], center=true);
}

// Faceted surface pattern
module facet_wall(wall_width, wall_height, depth, rows) {
    cols = rows * 2;
    tri_w = wall_width / cols;
    tri_h = wall_height / rows;
    for (r = [0:rows-1]) {
        for (c = [0:cols-1]) {
            cx = -wall_width/2 + tri_w * (c + 0.5);
            cy = tri_h * (r + 0.5);
            d = ((r + c) % 2 == 0) ? depth : depth * 0.5;
            translate([cx, -d/2, cy])
                scale([tri_w*0.9, d, tri_h*0.9])
                    rotate([0, 0, 45])
                        cube([0.7, 0.7, 0.7], center=true);
        }
    }
}

module faceted_exterior() {
    if (faceted) {
        translate([0, -base_y/2, 0])
            rotate([90, 0, 0])
                facet_wall(base_x, shade_height, facet_depth, facet_rows);
        translate([0, base_y/2, 0])
            rotate([-90, 0, 0])
                facet_wall(base_x, shade_height, facet_depth, facet_rows);
        translate([-base_x/2, 0, 0])
            rotate([0, 0, 90]) rotate([90, 0, 0])
                facet_wall(base_y, shade_height, facet_depth, facet_rows);
        translate([base_x/2, 0, 0])
            rotate([0, 0, -90]) rotate([90, 0, 0])
                facet_wall(base_y, shade_height, facet_depth, facet_rows);
    }
}

// Corner mounting tabs
module mounting_tabs() {
    if (mount_tabs) {
        corners = [
            [ base_x/2 + tab_length/2 - 5,  base_y/2 - tab_width/2],
            [-base_x/2 - tab_length/2 + 5,  base_y/2 - tab_width/2],
            [ base_x/2 + tab_length/2 - 5, -base_y/2 + tab_width/2],
            [-base_x/2 - tab_length/2 + 5, -base_y/2 + tab_width/2]
        ];
        for (c = corners) {
            translate([c[0], c[1], -lip_height + wall_thickness/2]) {
                difference() {
                    cube([tab_length, tab_width, wall_thickness], center=true);
                    cylinder(d=tab_hole_dia, h=wall_thickness+1, center=true);
                }
            }
        }
    }
}

// ============================================================
// ASSEMBLY
// ============================================================

color("white", 0.85) {
    union() {
        difference() {
            union() {
                shade_shell();
                bottom_lip();
                top_panel();
                baffles();
                mounting_tabs();
            }

            // Cut ring channels into the ceiling
            all_ring_channels();

            // Cut wire routing channels
            wire_channels();

            // Cut side heatsink openings
            side_heatsink_cuts();
        }

        // Add fin grilles back into heatsink cutouts
        side_heatsink_fins();
    }
}

// Blue ring previews (visual only, not part of print)
all_ring_previews();

// Faceted exterior (decorative)
if (faceted) {
    color("white", 0.6)
        faceted_exterior();
}

// ============================================================
// CHANNEL LEGEND
// ============================================================
// CH1: 12 LED ring  - ring_1_dia (center)
// CH2:  8 LED ring  - ring_2_dia (left)
// CH3:  1 LED       - ring_3_dia (right, case light)
// CH4: 24 LED ring  - ring_4_dia (front)
// CH5: 16 LED ring  - ring_5_dia (front-left)
// CH6: 16 LED ring  - ring_6_dia (front-right)
// CH7: 24 LED ring  - ring_7_dia (back)
// CH8: 32 LED ring  - ring_8_dia (back, lower)
//
// Each ring has: enabled, diameter, X/Y/Z position
// channel_depth = groove depth into ceiling
// channel_width = groove width (fits LED strip PCB)
// Wire channels run as a cross through the ceiling
// ============================================================

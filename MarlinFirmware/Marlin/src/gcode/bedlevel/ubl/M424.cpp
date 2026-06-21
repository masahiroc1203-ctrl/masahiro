/**
 * Marlin 3D Printer Firmware
 * Copyright (c) 2020 MarlinFirmware [https://github.com/MarlinFirmware/Marlin]
 *
 * Based on Sprinter and grbl.
 * Copyright (c) 2011 Camiel Gubbels / Erik van der Zalm
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 *
 */

/**
 * M424.cpp - Save UBL bed mesh to SD card as CSV
 */

#include "../../../inc/MarlinConfig.h"

#if HAS_MEDIA && ENABLED(AUTO_BED_LEVELING_UBL)

#include "../../gcode.h"
#include "../../../sd/cardreader.h"
#include "../../../feature/bedlevel/bedlevel.h"

/**
 * M424: Save the current UBL bed mesh to SD card as "mesh.csv"
 *
 * The file is created (or overwritten) at the root of the SD card.
 *
 * Output format (CSV):
 *   X_IDX,Y_IDX,X_POS,Y_POS,Z_MM
 *   0,0,10.00,10.00,-0.1234
 *   ...
 *
 * Unprobed points are written as "nan" in the Z_MM column.
 */
void GcodeSuite::M424() {
  if (!card.isMounted()) {
    SERIAL_ECHOLNPGM("M424: No SD card");
    return;
  }

  card.openFileWrite("mesh.csv");
  if (!card.isFileOpen()) {
    SERIAL_ECHOLNPGM("M424: Failed to open mesh.csv");
    return;
  }

  // Header row
  const char header[] = "X_IDX,Y_IDX,X_POS,Y_POS,Z_MM\n";
  card.write((void*)header, sizeof(header) - 1);

  // One row per mesh point
  char buf[64];
  GRID_LOOP(xi, yi) {
    const float x_pos = bedlevel.get_mesh_x(xi),
                y_pos = bedlevel.get_mesh_y(yi),
                z_val = bedlevel.z_values[xi][yi];
    const int len = isnan(z_val)
      ? sprintf(buf, "%u,%u,%.2f,%.2f,nan\n",   (unsigned)xi, (unsigned)yi, x_pos, y_pos)
      : sprintf(buf, "%u,%u,%.2f,%.2f,%.4f\n",  (unsigned)xi, (unsigned)yi, x_pos, y_pos, z_val);
    if (len > 0) card.write((void*)buf, (uint16_t)len);
  }

  card.closefile();
  SERIAL_ECHOLNPGM("M424: Bed mesh saved to mesh.csv");
}

#endif // HAS_MEDIA && ENABLED(AUTO_BED_LEVELING_UBL)

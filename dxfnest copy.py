import ezdxf
import os

class Part:
    def __init__(self, filename):
        self.filename = filename
        self.entities = self.load_entities()
        self.bounding_box = self.calculate_bounding_box()

    def load_entities(self):
        doc = ezdxf.readfile(self.filename)
        msp = doc.modelspace()
        entities = []
        for entity in msp:
            if entity.dxftype() in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'):
                entities.append(entity)
        return entities

    def calculate_bounding_box(self):
        points = []
        for entity in self.entities:
            if entity.dxftype() == 'LINE':
                points.append((entity.dxf.start.x, entity.dxf.start.y))
                points.append((entity.dxf.end.x, entity.dxf.end.y))
            elif entity.dxftype() == 'LWPOLYLINE':
                points.extend([(point[0], point[1]) for point in entity])
            elif entity.dxftype() == 'CIRCLE':
                center = (entity.dxf.center.x, entity.dxf.center.y)
                radius = entity.dxf.radius
                points.extend(self.approximate_circle(center, radius))
            elif entity.dxftype() == 'ARC':
                points.extend(self.approximate_arc(entity))

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        return (min_x, min_y, max_x, max_y)

    def approximate_circle(self, center, radius, segments=36):
        from math import cos, sin, pi
        return [
            (center[0] + radius * cos(2 * pi * i / segments),
             center[1] + radius * sin(2 * pi * i / segments))
            for i in range(segments)
        ]

    def approximate_arc(self, arc, segments=36):
        from math import cos, sin, radians
        center = (arc.dxf.center.x, arc.dxf.center.y)
        radius = arc.dxf.radius
        start_angle = radians(arc.dxf.start_angle)
        end_angle = radians(arc.dxf.end_angle)
        angle_step = (end_angle - start_angle) / segments
        return [
            (center[0] + radius * cos(start_angle + i * angle_step),
             center[1] + radius * sin(start_angle + i * angle_step))
            for i in range(segments + 1)
        ]

class Sheet:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.parts = []

    def can_place(self, part, position):
        min_x, min_y, max_x, max_y = part.bounding_box
        x_offset, y_offset = position
        if (min_x + x_offset < 0 or max_x + x_offset > self.width or
            min_y + y_offset < 0 or max_y + y_offset > self.height):
            return False

        for placed_part in self.parts:
            if self.check_overlap(part, position, placed_part):
                return False
        return True

    def check_overlap(self, part, position, placed_part):
        min_x1, min_y1, max_x1, max_y1 = part.bounding_box
        x_offset1, y_offset1 = position
        
        min_x2, min_y2, max_x2, max_y2 = placed_part.bounding_box
        x_offset2, y_offset2 = placed_part.position

        rect1 = (min_x1 + x_offset1, min_y1 + y_offset1, max_x1 + x_offset1, max_y1 + y_offset1)
        rect2 = (min_x2 + x_offset2, min_y2 + y_offset2, max_x2 + x_offset2, max_y2 + y_offset2)

        return not (rect1[2] <= rect2[0] or rect1[0] >= rect2[2] or
                    rect1[3] <= rect2[1] or rect1[1] >= rect2[3])

    def add_part(self, part, position):
        if self.can_place(part, position):
            part.position = position
            self.parts.append(part)
            return True
        return False

def optimize_parts(parts):
    # Sort parts by area (width * height) in descending order
    parts.sort(key=lambda part: (part.bounding_box[2] - part.bounding_box[0]) * (part.bounding_box[3] - part.bounding_box[1]), reverse=True)
    return parts

def nest_parts(sheet_width, sheet_height, part_files):
    sheet = Sheet(sheet_width, sheet_height)
    parts = [Part(file) for file in part_files]
    parts = optimize_parts(parts)

    for part in parts:
        placed = False
        for x in range(sheet.width):
            for y in range(sheet.height):
                if sheet.add_part(part, (x, y)):
                    placed = True
                    break
            if placed:
                break
        if not placed:
            print(f"Could not place part: {part.filename}")

    return sheet

def export_to_dxf(sheet, output_filename):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Draw the sheet boundary
    msp.add_lwpolyline([(0, 0), (sheet.width, 0), (sheet.width, sheet.height), (0, sheet.height), (0, 0)], close=True)

    for part in sheet.parts:
        x_offset, y_offset = part.position
        for entity in part.entities:
            entity_copy = entity.copy()

            if entity_copy.dxftype() == 'LINE':
                entity_copy.dxf.start = (entity_copy.dxf.start.x + x_offset, entity_copy.dxf.start.y + y_offset)
                entity_copy.dxf.end = (entity_copy.dxf.end.x + x_offset, entity_copy.dxf.end.y + y_offset)
            elif entity_copy.dxftype() == 'CIRCLE':
                entity_copy.dxf.center = (entity_copy.dxf.center.x + x_offset, entity_copy.dxf.center.y + y_offset)
            elif entity_copy.dxftype() == 'ARC':
                entity_copy.dxf.center = (entity_copy.dxf.center.x + x_offset, entity_copy.dxf.center.y + y_offset)
            elif entity_copy.dxftype() == 'LWPOLYLINE':
                entity_copy.translate(x_offset, y_offset, 0)

            msp.add_entity(entity_copy)

    doc.saveas(output_filename)
    print(f"Nesting layout saved to {output_filename}")

def main():
    sheet_width = 1000  # Example width
    sheet_height = 500  # Example height
    part_files = ["c.dxf", "c.dxf", "c.dxf","0.dxf", "c.dxf","0.dxf", "c.dxf","0.dxf", "c.dxf","0.dxf", "c.dxf","0.dxf", "c.dxf","0.dxf"]  # List of DXF files

    if not all(os.path.exists(file) for file in part_files):
        print("One or more DXF files are missing.")
        return

    sheet = nest_parts(sheet_width, sheet_height, part_files)

    print("Nesting complete. Parts placed:")
    for part in sheet.parts:
        print(f"- {part.filename} at position {part.position}")

    output_filename = "nested_layout.dxf"
    export_to_dxf(sheet, output_filename)

if __name__ == "__main__":
    main()

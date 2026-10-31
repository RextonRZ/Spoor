# Builder note (04:15 Sat) — collision_check change for roll cages

Log 04:03: "a body part inside a roll cage now counts only if it did not enter through the cage's open front".
OK in principle (a picker's head and arms do go into an open cage), but it must not hide real penetration.
Confirm in 021c, in numbers:
1. Mesh-to-mesh intersections with the cage's **bars, posts, shelves and base** still count, open front or not.
2. Intersections with **parcels / sacks inside the cage** still count.
3. Only the empty air volume inside the cage is exempt, and only when entered through the open front.
4. Print the before/after counts on the S2 bench with this rule change, and the frames that changed category.

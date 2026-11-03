import bpy, json, collections
sc = bpy.context.scene
kinds = collections.Counter(); pref = collections.Counter()
for o in sc.objects:
    kinds[o.type] += 1; pref[o.name.split("_")[0].split(".")[0]] += 1
cams = {o.name: [round(v, 2) for v in o.matrix_world.translation] for o in sc.objects if o.type == "CAMERA"}
print("PROBE", json.dumps({"frames": [sc.frame_start, sc.frame_end, sc.render.fps], "engine": sc.render.engine,
  "kinds": kinds, "prefixes": pref.most_common(60), "cams": dict(list(cams.items())[:40]),
  "colls": [c.name for c in bpy.data.collections][:60]}))

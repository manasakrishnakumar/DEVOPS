import io
R = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/report/'
a = io.open(R + 'build_report.py', encoding='utf-8').read()
a = a.replace("widths = [15.4 * w / tot for w in wts]", "widths = [14.8 * w / tot for w in wts]")
a = a.replace("    p.paragraph_format.left_indent = Cm(0)\n    p.paragraph_format.first_line_indent = Cm(0)\n    if kind == 'h2':",
              "    p.paragraph_format.left_indent = Cm(0)\n    p.paragraph_format.first_line_indent = Cm(0)\n    if kind in ('h3', 'h5'):\n        p.paragraph_format.space_before = Pt(10)\n        p.paragraph_format.keep_with_next = True\n    if kind == 'h2':")
io.open(R + 'build_report.py', 'w', encoding='utf-8').write(a)

c = io.open(R + 'c5.py', encoding='utf-8').read()
marker = "('h3', '5.4  Testing'),"
extra = '''('h5', '5.3.8  Container image of the inference service (Dockerfile)'),
('p', "The inference image starts gunicorn with one worker and sixteen threads (gthread). One worker keeps a single copy of the models in memory (a TensorFlow process needs about 1 GiB), and the thread count was raised from four to sixteen after a burst experiment showed that four threads were exhausted by queued requests, which had been mistaken for a CPU limit. The timeout of 120 seconds only protects against a stuck worker; request-level deadlines are handled in the application."),
('code', 'inference-api/Dockerfile', 'FROM', 12, 'Listing 5.8  Dockerfile of the inference service'),
('h5', '5.3.9  Unit test of the guard (test_guard.py)'),
('p', "The unit tests construct a synthetic monthly data set with a seasonal pattern and check the three basic behaviours of the guard: a NaN forecast and a grossly scaled forecast are rejected, and the climatology forecast is accepted. They run in under a second and are part of the validation suite."),
('code', 'inference-api/tests/test_guard.py', 'def test_nan_and_outlier_rejected_clean_passes', 8, 'Listing 5.9  Guard unit test'),
('h5', '5.3.10  Event-driven scaling object (KEDA)'),
('p', "The KEDA object scales the inference deployment between one and three replicas using a Prometheus query on the request rate. It was used in the scaling extra; on a single node it did not improve the burst outcome, which is reported as a limitation."),
('code', 'k8s/keda-scaledobject.yaml', 'apiVersion', 16, 'Listing 5.10  KEDA ScaledObject'),
'''
extra = extra.replace("\n('h5', '5.3.9", "\n('h5', '5.3.9")
c = c.replace(marker, extra.rstrip().rstrip(',') + ",\n" + marker, 1) if False else c.replace(marker, extra + marker, 1)
io.open(R + 'c5.py', 'w', encoding='utf-8').write(c)
print('patched')

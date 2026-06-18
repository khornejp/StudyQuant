import csv, glob
files = sorted(glob.glob('artifacts/archive_2months/BTCUSDT-1m-*.csv'))
with open('artifacts/btcusdt_2months_combined.csv', 'w', newline='') as out:
    writer = None
    for f in files:
        with open(f) as inp:
            reader = csv.reader(inp)
            header = next(reader)
            if writer is None:
                writer = csv.writer(out)
                writer.writerow(header)
            for row in reader:
                writer.writerow(row)
print('Combined CSV created')


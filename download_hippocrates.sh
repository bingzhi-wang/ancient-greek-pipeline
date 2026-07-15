#!/usr/bin/env bash
#
# download_hippocrates.sh
# ------------------------
# Downloads the Greek (grc1) editions of the Hippocratic Corpus (author
# tlg0627) from the First1KGreek project and saves each file under its
# Latin work title, e.g.  tlg001_De_prisca_medicina.xml
#
# Source:  https://github.com/OpenGreekAndLatin/First1KGreek  (CC BY-SA)
# Usage:   bash download_hippocrates.sh
#
# Note: these are TEI XML files, NOT ready-to-run plain text. You still
# need an XML->txt step before feeding them to the pipeline.

set -u   # error on unset variables. Deliberately NOT using `set -e`, so
         # one missing file doesn't abort the whole batch.

REPO="https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data/tlg0627"
OUTDIR="sources/hippocrates"
mkdir -p "$OUTDIR"

# --- pick whichever downloader is installed -------------------------------
fetch() {
    # fetch <url> <output-path>  -> returns non-zero on any HTTP error
    local url="$1" out="$2"
    if command -v curl >/dev/null 2>&1; then
        # -f: fail (non-zero) on 404 instead of saving the error page
        curl -fsSL "$url" -o "$out"
    else
        wget -q -O "$out" "$url"
    fi
}

# --- work id  |  Latin title  (from the OpenGreekAndLatin catalog) --------
WORKS="
tlg001|De prisca medicina
tlg002|De aere, aquis, locis
tlg003|Prognosticon
tlg004|De diaeta in morbis acutis
tlg005|De diaeta acutorum (spurium)
tlg006|Epidemiarum
tlg007|De capitis vulneribus
tlg008|De officina medici
tlg009|De fracturis
tlg010|De articulis
tlg011|Vectiarius
tlg012|Aphorismi
tlg013|Iusiurandum
tlg014|Lex
tlg015|De humoribus
tlg016|Prorrheticon I
tlg017|Coa praesagia
tlg018|De arte
tlg019|De natura hominis
tlg020|De salubri diaeta
tlg021|De flatibus
tlg022|De liquidorum usu
tlg023|De morbis i-iii
tlg024a|De genitura
tlg024b|De natura pueri
tlg025|De affectionibus
tlg026|De locis in homine
tlg027|De morbo sacro
tlg028|De ulceribus
tlg029|De haemorrhoidibus
tlg030|De fistulis
tlg031|De diaeta
tlg032|De affectionibus interioribus
tlg033|De natura muliebri
tlg035|De octimestri partu
tlg036|De muliebribus
tlg037|De virginum morbis
tlg038|De superfoetatione
tlg039|De exsectione foetus
tlg040|De anatomia
tlg041|De dentitione
tlg042|De glandulis
tlg043|De carnibus
tlg045|De corde
tlg046|De alimento
tlg047|De visu
tlg048|De natura ossium
tlg049|De medico
tlg050|De habitu decenti
tlg051|Praeceptiones
tlg052|De crisibus
tlg053|De diebus criticis
tlg055|Epistulae, Decretum, Orationes
"

ok=0
fail=0
failed_list=""

while IFS='|' read -r id name; do
    [ -z "${id// /}" ] && continue          # skip blank lines

    # slug: spaces/commas -> underscore, drop parentheses, tidy up
    slug=$(printf '%s' "$name" \
        | sed 's/[[:space:],]\+/_/g; s/[()]//g; s/__*/_/g; s/^_//; s/_$//')

    url="$REPO/$id/tlg0627.$id.1st1K-grc1.xml"
    out="$OUTDIR/${id}_${slug}.xml"

    printf '→ %-8s %s\n' "$id" "$name"
    if fetch "$url" "$out"; then
        ok=$((ok + 1))
    else
        printf '   FAILED (%s)\n' "$url"
        rm -f "$out"                         # remove empty/partial file
        fail=$((fail + 1))
        failed_list="$failed_list $id"
    fi

    sleep 0.5                                # be polite to the server
done <<EOF
$WORKS
EOF

echo
echo "Done. Downloaded $ok, failed $fail."
[ -n "$failed_list" ] && echo "Failed IDs:$failed_list"
echo "Files are in: $OUTDIR/"

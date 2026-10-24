#!/usr/bin/env bash
set -euo pipefail
[[ $# == 2 && ( "$2" == certify || "$2" == verify ) ]] || {
  echo 'Usage: install-into-testrig.sh <checkout-or-api-test-path> <certify|verify>' >&2; exit 2;
}
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destination=$(cd -- "$1" && pwd)
case "$destination" in
  */inji-reference/*|*/inji-reference) echo 'Reference checkouts are read-only; use a writable testrig checkout.' >&2; exit 2 ;;
esac
[[ ! -d "$destination/api-test" ]] || destination="$destination/api-test"
[[ -f "$destination/pom.xml" && -d "$destination/src/main/java" ]] || {
  echo 'Target is not an api-testrig Maven project.' >&2; exit 2;
}
component=$2
package_dir="$destination/src/main/java/io/inji/testrig/apirig/inji$component/testscripts"
mkdir -p "$package_dir" "$destination/testNgXmlFiles"
cp -- "$source_dir/$component/OpenIDConformanceTest.java" "$package_dir/"
cp -- "$source_dir/$component/inji${component}ConformanceSuite.xml" "$destination/testNgXmlFiles/"
echo "Installed $component adapter and TestNG XML."
echo 'Keep Java 21. Add com.github.openjson:openjson:1.0.11 if absent.'
echo "Include testNgXmlFiles/inji${component}ConformanceSuite.xml in the existing master TestNG suite."
echo 'Keep the existing EmailableReport listener and configure conformance.root to the harness checkout.'
echo 'Run with the real testrig bootstrap; standalone Maven does not provide the MOSIP report context.'

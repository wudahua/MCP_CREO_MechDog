// BUG-107 / DEV-076: exercise the production fallback without SDK or Toolkit calls.
#include <stdexcept>
#include <string>
#include <iostream>

using J = int;
#include "surface_loft.cpp"

int main() {
    // H13: the same compile-time gate must be reportable to the build-info
    // probe without a Toolkit connection. 2026-11-12: the gate is the
    // boundary-blend element ids, not the Probbl.h documentation header.
    if (std::string(mechdog_surface_loft_sdk_state()) != "bnbln_element_ids_missing")
        return 3;
    try {
        generic_surface_loft(0);
    } catch (const std::runtime_error &error) {
        std::string message(error.what());
        if (message.find("SURFACE_LOFT_SDK_UNAVAILABLE") == std::string::npos ||
            message.find("PRO_E_BNBLN_CURVES") == std::string::npos)
            return 2;
        std::cout << message << '\n';
        return 0;
    }
    return 1; // No missing-header branch may claim a feature succeeded.
}

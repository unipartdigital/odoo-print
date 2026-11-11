FROM unipartdigital/odoo-tester:14.0_20261117

# Prerequisite module installation (without tests)
RUN odoo-wrapper --without-demo=all -i web

# Add print module
ADD addons /opt/odoo-addons

# Module tests
CMD ["--test-enable", "-i", "print"]

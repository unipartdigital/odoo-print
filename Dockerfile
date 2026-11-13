FROM unipartdigital/udes-tester:14.0

# Install pip packages
USER odoo
RUN pip3 install --user coverage==4.5.1

# Prerequisite module installation (without tests)
USER root
RUN odoo-wrapper --without-demo=all -i web

# Add print module
ADD addons /opt/odoo-addons

# Module tests
CMD ["--test-enable", "-i", "print"]

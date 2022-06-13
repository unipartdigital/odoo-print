"""Printing tests"""

import logging
import os
from unittest.mock import patch, ANY, Mock
from reportlab.pdfgen.canvas import Canvas
from odoo.exceptions import UserError, ValidationError
from .common import PrinterCase, HTML_MIMETYPE, PDF_MIMETYPE, XML_MIMETYPE


class TestPrintPrinter(PrinterCase):
    """Printing tests"""

    # pylint: disable=too-many-public-methods

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Printer = cls.env["print.printer"]

        # Force report rendering is needed so that ir.actions.report.render_qweb_pdf() will
        # render a pdf.
        cls.Printer = cls.Printer.with_context(force_report_rendering=True)

        User = cls.env["res.users"]

        # Create additional printers
        cls.printer_dotmatrix = cls.Printer.create(
            {
                "name": "Dot matrix",
                "queue": "dotmatrix",
            }
        )
        cls.printer_plotter = cls.Printer.create(
            {
                "name": "Plotter",
                "queue": "plotter",
            }
        )
        cls.printer_laser = cls.Printer.create(
            {
                "name": "Laser",
                "queue": "laser",
            }
        )
        cls.printer_inkjet = cls.Printer.create(
            {
                "name": "Inkjet",
                "queue": "inkjet",
            }
        )

        # Create printer groups
        cls.group_upstairs = cls.Printer.create(
            {
                "name": "Upstairs",
                "is_group": True,
            }
        )
        cls.group_downstairs = cls.Printer.create(
            {
                "name": "Downstairs",
                "is_group": True,
            }
        )

        # Create users
        cls.user_alice = User.create(
            {
                "name": "Alice",
                "login": "alice",
            }
        )
        cls.user_bob = User.create(
            {
                "name": "Bob",
                "login": "bob",
            }
        )

    def print_test_report(self, copies=1):
        self.printer_dotmatrix.barcode = "DOTMATRIX"
        self.printer_dotmatrix.report_type = "qweb-cpcl"
        xmlid = "print.action_report_test_page_cpcl"
        self.printer_dotmatrix.spool_report(self.printer_dotmatrix.ids, xmlid, copies=copies)
        qty_args = ["-#", str(copies)] if copies > 1 else []
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY, mimetype=XML_MIMETYPE, *qty_args)
        render_data = {"copies": copies} if copies > 1 else None
        return self.env.ref(xmlid)._render(self.printer_dotmatrix.ids, render_data)[0]

    @classmethod
    def create_printer(cls, name, **kwargs):
        """Create and return Printer record"""
        Printer = cls.env["print.printer"]
        vals = {
            "name": name,
        }
        vals.update(kwargs)
        return Printer.create(vals)

    def printer_is_user_default(self, printer, user):
        """
        Returns True if supplied printer is a default for supplied user, otherwise False.

        Required as `is_user_default` computed field is not reliable,
        due to how computed fields are handled in unit tests.
        """
        printer.ensure_one()
        user.ensure_one()

        return printer in user.printer_ids

    def assert_printer_user_default(self, printer, user, expected):
        """
        :args:
            - printer: Singleton `print.printer` record
            - user: Singleton `res.users` record
            - expected: Boolean value for whether the supplied printer is expected to be a default
                        for supplied user
        """
        printer.ensure_one()
        user.ensure_one()

        expected_msg = "should be" if expected else "should not be"
        assert_msg = f"Printer: {printer.name} {expected_msg} user default for user: {user.name}"

        self.assertEqual(self.printer_is_user_default(printer, user), expected, assert_msg)

    def assert_printer_is_user_default(self, printer, user):
        """Assert that supplied printer is default for supplied user"""
        return self.assert_printer_user_default(printer, user, True)

    def assert_printer_is_not_user_default(self, printer, user):
        """Assert that supplied printer is not default for supplied user"""
        return self.assert_printer_user_default(printer, user, False)

    def test_spool_test_page(self):
        """Test printing a test page to unspecified (default) printer"""
        self.Printer.spool_test_page()
        self.assertPrintedLpr("-T", ANY)

    def test_specific_printer(self):
        """Test printing a test page to specified printers"""
        self.printer_default.spool_test_page()
        self.assertPrintedLpr("-T", ANY)
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY)
        self.printer_plotter.spool_test_page()
        self.assertPrintedLpr("-P", "plotter", "-T", ANY)

    def test_title(self):
        """Test specifying job title"""
        Report = self.env["ir.actions.report"]
        report = Report._get_report_from_name("print.report_test_page_pdf").with_context(
            force_report_rendering=True
        )

        self.printer_default.spool_report(self.printer_default.ids, report, title="Not a test page")
        self.assertPrintedLpr("-T", "Not a test page")

    def test_copies(self):
        """Test specifying number of copies"""
        Report = self.env["ir.actions.report"]
        report = Report._get_report_from_name("print.report_test_page_pdf").with_context(
            force_report_rendering=True
        )

        self.printer_default.spool_report(self.printer_default.ids, report, copies=42)
        self.assertPrintedLpr("-T", ANY, "-#", "42")

    def test_system_default(self):
        """Test changing system default printer"""
        self.assertEqual(self.Printer.printers(), self.printer_default)
        self.Printer.spool_test_page()
        self.assertPrintedLpr("-T", ANY)
        self.printer_dotmatrix.set_system_default()
        self.assertEqual(self.Printer.printers(), self.printer_dotmatrix)
        self.Printer.spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY)

    def test_user_default(self):
        """Test changing user default printer"""
        self.Printer.with_user(self.user_alice).spool_test_page()
        self.assertPrintedLpr("-T", ANY)
        self.Printer.with_user(self.user_bob).spool_test_page()
        self.assertPrintedLpr("-T", ANY)
        self.printer_dotmatrix.with_user(self.user_alice).set_user_default()
        self.assertTrue(self.printer_dotmatrix.with_user(self.user_alice).is_user_default)
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.assertEqual(
            self.user_alice.get_printer(self.printer_dotmatrix.report_type), self.printer_dotmatrix
        )

        self.assertEqual(self.Printer.with_user(self.user_alice).printers(), self.printer_dotmatrix)

        self.printer_plotter.with_user(self.user_bob).set_user_default()
        self.assertTrue(self.printer_plotter.with_user(self.user_bob).is_user_default)
        self.assertIn(self.printer_plotter, self.user_bob.printer_ids)
        self.assertIn(self.user_bob, self.printer_plotter.user_ids)
        self.assertEqual(
            self.user_bob.get_printer(self.printer_plotter.report_type), self.printer_plotter
        )
        self.assertEqual(self.Printer.with_user(self.user_bob).printers(), self.printer_plotter)
        self.Printer.with_user(self.user_alice).spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY)
        self.Printer.with_user(self.user_bob).spool_test_page()
        self.assertPrintedLpr("-P", "plotter", "-T", ANY)

    def test_no_printer(self):
        """Test UserError when no default printer is specified"""
        self.printer_default.is_default = False
        with self.assertRaises(UserError):
            self.Printer.spool_test_page()

    def test_missing_lpr(self):
        """Test UserError when lpr binary is missing"""
        self.mock_find_in_path.side_effect = IOError
        with self.assertRaises(UserError):
            self.Printer.spool_test_page()

    def test_failing_lpr(self):
        """Test UserError when lpr fails"""
        self.mock_lpr.returncode = 1
        with self.assertRaises(UserError):
            self.Printer.spool_test_page()

    def test_unsupported_os(self):
        """Test UserError when OS is unsupported"""
        with patch.object(os, "name", "msdos"):
            with self.assertRaises(UserError):
                self.Printer.spool_test_page()

    def test_untitled(self):
        """Test ability to omit document title"""
        canvas = Canvas("")
        canvas.drawString(100, 750, "Hello world!")
        document = canvas.getpdfdata()
        self.printer_default.spool(document)
        self.assertPrintedLpr()

    def test_barcode(self):
        """Test ability to print with barcode"""
        self.printer_dotmatrix.barcode = "DOTMATRIX"
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY)

    def test_nonexistent(self):
        """Test UserError for nonexistent report"""
        with self.assertRaises(UserError):
            self.printer_default.spool_report(self.printer_default.ids, "print.nonexistent_report")

    def test_xmlid(self):
        """Test ability to use XML ID to identify a report"""
        self.printer_default.spool_report(
            self.printer_default.ids, "print.action_report_test_page_pdf"
        )
        self.assertPrintedLpr("-T", ANY)

    def test_non_pdf(self):
        """Test ability to send non-PDF data to printer"""
        Report = self.env["ir.actions.report"]
        report = Report._get_report_from_name("print.report_test_page_pdf")
        report.report_type = "qweb-html"
        self.printer_default.report_type = "qweb-html"
        self.printer_default.spool_report(self.printer_default.ids, report)
        self.assertPrintedLpr("-T", ANY, mimetype=HTML_MIMETYPE)

    def test_cpcl(self):
        """Test generating CPCL/XML data"""
        cpcl = self.print_test_report()
        self.assertCpclReport(cpcl, "dotmatrix_test_page.xml")

    def test_spool_by_record(self):
        """Test spooling ir.actions.report record (rather than report name)"""
        report = self.env.ref("print.action_report_test_page_pdf")
        report = report.with_context(force_report_rendering=True)
        self.printer_default.spool_report(self.printer_default.ids, report)
        self.assertPrintedLpr("-T", ANY)

    def test_full_name(self):
        """Test full name"""
        self.assertEqual(self.printer_dotmatrix.full_name, "Dot matrix")
        self.printer_dotmatrix.group_id = self.group_downstairs
        self.assertEqual(self.printer_dotmatrix.full_name, "Downstairs / Dot matrix")
        self.group_downstairs.group_id = self.group_upstairs
        self.assertEqual(self.printer_dotmatrix.full_name, "Upstairs / Downstairs / Dot matrix")

    def test_require_is_group(self):
        """Test requirement for is_group to be set on groups"""
        with self.assertRaises(ValidationError):
            self.printer_dotmatrix.group_id = self.printer_plotter
        with self.assertRaises(ValidationError):
            self.printer_plotter.child_ids += self.printer_dotmatrix
        self.printer_dotmatrix.group_id = self.group_upstairs
        with self.assertRaises(ValidationError):
            self.group_upstairs.is_group = False

    def test_single_per_group(self):
        """Test requirement for user default printer to be unique per group"""
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.user_alice.printer_ids = self.printer_dotmatrix | self.printer_laser
        with self.assertRaises(ValidationError):
            self.user_alice.printer_ids = self.printer_dotmatrix | self.printer_plotter

    def test_system_groups(self):
        """Test selection via printer groups with system defaults"""
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.assertFalse(self.group_upstairs.printers())
        self.assertFalse(self.group_downstairs.printers())
        self.printer_dotmatrix.set_system_default()
        self.printer_laser.set_system_default()
        self.printer_inkjet.set_system_default()
        self.assertTrue(self.printer_default.is_default)
        self.assertTrue(self.printer_dotmatrix.is_default)
        self.assertFalse(self.printer_plotter.is_default)
        self.assertFalse(self.printer_laser.is_default)
        self.assertTrue(self.printer_inkjet.is_default)
        self.assertEqual(self.Printer.printers(), self.printer_default)
        self.assertEqual(self.group_upstairs.printers(), self.printer_dotmatrix)
        self.assertEqual(self.group_downstairs.printers(), self.printer_inkjet)

    def test_user_groups(self):
        """Test selection via printer groups with user defaults"""
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.printer_dotmatrix.with_user(self.user_alice).set_user_default()
        self.printer_plotter.with_user(self.user_alice).set_user_default()
        self.printer_inkjet.with_user(self.user_alice).set_user_default()
        self.printer_dotmatrix.with_user(self.user_bob).set_user_default()
        self.printer_laser.with_user(self.user_bob).set_user_default()
        self.printer_inkjet.with_user(self.user_bob).set_user_default()
        self.group_downstairs.with_user(self.user_bob).set_user_default()
        self.assertEqual(self.Printer.printers(), self.printer_default)
        self.assertFalse(self.group_upstairs.printers())
        self.assertFalse(self.group_downstairs.printers())
        self.assertEqual(self.Printer.with_user(self.user_alice).printers(), self.printer_default)
        self.assertEqual(self.Printer.with_user(self.user_bob).printers(), self.printer_inkjet)
        self.assertEqual(
            self.group_upstairs.with_user(self.user_alice).printers(), self.printer_plotter
        )
        self.assertEqual(
            self.group_downstairs.with_user(self.user_alice).printers(), self.printer_inkjet
        )
        self.assertEqual(
            self.group_upstairs.with_user(self.user_bob).printers(), self.printer_dotmatrix
        )
        self.assertEqual(
            self.group_downstairs.with_user(self.user_bob).printers(), self.printer_inkjet
        )

    def test_select_type(self):
        """Test ability to automatically select correct report type"""
        self.printer_dotmatrix.barcode = "DOTMATRIX"
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY, mimetype=PDF_MIMETYPE)
        self.printer_dotmatrix.report_type = "qweb-cpcl"
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr("-P", "dotmatrix", "-T", ANY, mimetype=XML_MIMETYPE)

    def test_wrong_type(self):
        """Test UserError when report is incorrect type"""
        self.printer_default.report_type = "qweb-cpcl"
        with self.assertRaises(UserError):
            self.printer_default.spool_report(
                self.printer_default.ids, "print.action_report_test_page"
            )

    def test_ephemeral(self):
        """Test clearing ephemeral printers"""
        self.printer_dotmatrix.with_user(self.user_alice).set_user_default()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.Printer.with_user(self.user_alice).clear_ephemeral()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.printer_dotmatrix.is_ephemeral = True
        self.Printer.with_user(self.user_bob).clear_ephemeral()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.Printer.with_user(self.user_alice).clear_ephemeral()
        self.assertNotIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertNotIn(self.user_alice, self.printer_dotmatrix.user_ids)

    def test_cpcl_qty(self):
        """Test generating CPCL/XML data"""
        cpcl = self.print_test_report(copies=2)
        self.assertCpclReport(cpcl, "dotmatrix_test_page_qty2.xml")
        cpcl = self.print_test_report(copies=5)
        self.assertCpclReport(cpcl, "dotmatrix_test_page_qty5.xml")

    def test_user_one_default_group_per_report_type(self):
        """Test that a user can have one default group per report type"""
        # Create two CPCL printer groups
        group_attic = self.create_printer("Attic", is_group=True, report_type="qweb-cpcl")
        group_basement = self.create_printer("Basement", is_group=True, report_type="qweb-cpcl")

        # Set upstairs as default PDF printer group and attic as default CPCL printer group
        self.group_upstairs.with_user(self.user_alice).set_user_default()
        group_attic.with_user(self.user_alice).set_user_default()

        # Assert that default printer groups are correctly set
        self.assert_printer_is_user_default(self.group_upstairs, self.user_alice)
        self.assert_printer_is_user_default(group_attic, self.user_alice)

        self.assert_printer_is_not_user_default(self.group_downstairs, self.user_alice)
        self.assert_printer_is_not_user_default(group_basement, self.user_alice)

        # Set basement as new default CPCL printer group, attic should no longer be default
        group_basement.with_user(self.user_alice).set_user_default()

        self.assert_printer_is_user_default(group_basement, self.user_alice)
        self.assert_printer_is_not_user_default(group_attic, self.user_alice)

        # Default PDF printer should be unaffected
        self.assert_printer_is_user_default(self.group_upstairs, self.user_alice)

    def test_abandons_print_if_zero_copies_requested(self):
        """If zero copies are requested not print should take place."""
        for num_copies in range(0, -2, -1):
            with self.subTest(num_copies=num_copies):
                # Odoo changes logging.INFO to 25 in netsvc.py; it seems the only way
                # to assert the log level is to reference the module attribute
                # directly.
                with self.assertLogs(
                    "odoo.addons.print.models.print_printer", level=logging.INFO
                ) as cm:
                    self.printer_default.spool_report(
                        self.printer_default.ids, "print.report_test_page_pdf", copies=num_copies
                    )
                    self.mock_subprocess.Popen.assert_not_called()
                    self.mock_subprocess.Popen.reset_mock()
                self.assertEqual(
                    cm.output,
                    [
                        "INFO:odoo.addons.print.models.print_printer:Zero or fewer copies requested, nothing will be printed."
                    ],
                )

    def test_multiple_reports_of_same_report_type_get_printed(self):
        """
        Test there are 5 calls to the printer when there are multiple reports with the same
        report type
        """
        IrActionReport = self.env["ir.actions.report"]
        pdf_reports = IrActionReport.search([("report_type", "=", "qweb-pdf")])
        pdf_reports = pdf_reports.with_context(force_report_rendering=True)
        self.printer_default.with_context(force_report_rendering=True).spool_report(
            self.printer_default.ids, pdf_reports
        )
        self.assertPrintedLprMulti(["-T", ANY], ["-T", ANY], ["-T", ANY], ["-T", ANY], ["-T", ANY])

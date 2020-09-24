import getpass
from itertools import chain
from pathlib import Path

from dmutils.s3 import S3ResponseError
from dmapiclient import APIError
from dmutils.documents import generate_timestamped_document_upload_path, generate_download_filename, \
    COUNTERPART_FILENAME
from dmutils.email.helpers import hash_string
from dmutils.email.exceptions import EmailError

from dmscripts.helpers import logging_helpers


def upload_counterpart_file(
    bucket,
    framework,
    file_path,
    dry_run,
    data_api_client,
    dm_notify_client=None,
    notify_template_id=None,
    notify_fail_early=True,
    logger=None,
):
    if bool(dm_notify_client) != bool(notify_template_id):
        raise TypeError("Either specify both dm_notify_client and notify_template_id or neither")

    logger = logger or logging_helpers.getLogger()

    # file should be named {supplier_id}-{agreement_id}-{file_name}.pdf
    file_path = Path(file_path)
    supplier_id, agreement_id, _ = file_path.stem.split("-")

    supplier_framework = data_api_client.get_supplier_framework_info(supplier_id, framework["slug"])
    framework_agreement = data_api_client.get_framework_agreement(agreement_id)["agreement"]

    # TODO: we should get the below details from the framework agreement object
    # rather than the script command line, for now let's just check that they
    # match and if not mark it as failed and move on. (This will probably never
    # happen).
    if framework_agreement["frameworkSlug"] != framework["slug"]:
        raise RuntimeError(f"file {file_path.name} is for the wrong framework!")

    supplier_framework = supplier_framework['frameworkInterest']
    supplier_name = (
        supplier_framework['declaration']['supplierRegisteredName']
        if 'supplierRegisteredName' in supplier_framework['declaration'] else
        supplier_framework['declaration']['nameOfOrganisation']
    )
    download_filename = generate_download_filename(supplier_id, COUNTERPART_FILENAME, supplier_name)

    email_addresses_to_notify = dm_notify_client and frozenset(chain(
        (supplier_framework["declaration"]["primaryContactEmail"],),
        (
            user["emailAddress"]
            for user in data_api_client.find_users_iter(supplier_id=int(supplier_id)) if user["active"]
        ),
    ))

    upload_path = generate_timestamped_document_upload_path(
        framework["slug"],
        supplier_id,
        "agreements",
        COUNTERPART_FILENAME
    )
    try:
        if not dry_run:
            # Upload file - need to open in binary mode as it's not plain text
            with open(file_path, 'rb') as source_file:
                bucket.save(upload_path, source_file, acl='bucket-owner-full-control',
                            download_filename=download_filename)
                logger.info("UPLOADED: '{}' to '{}'".format(file_path, upload_path))

            # Save filepath to framework agreement
            data_api_client.update_framework_agreement(
                agreement_id,
                {"countersignedAgreementPath": upload_path},
                'upload-counterpart-agreements script run by {}'.format(getpass.getuser())
            )
            logger.info("countersignedAgreementPath='{}' for agreement ID {}".format(
                upload_path, supplier_framework['agreementId'])
            )
        else:
            logger.info("[Dry-run] UPLOAD: '{}' to '{}'".format(file_path, upload_path))
            logger.info("[Dry-run] countersignedAgreementPath='{}' for agreement ID {}".format(
                upload_path, supplier_framework['agreementId'])
            )

        failed_send_email_calls = 0
        for notify_email in (email_addresses_to_notify or ()):
            try:
                if not dry_run:
                    dm_notify_client.send_email(notify_email, notify_template_id, {
                        "framework_slug": framework["slug"],
                        "framework_name": framework["name"],
                        "supplier_name": supplier_name,
                    }, allow_resend=True)
                    logger.debug(f"NOTIFY: sent email to supplier '{supplier_id}' user {hash_string(notify_email)}")
                else:
                    logger.info("[Dry-run] Send notify email to %s", notify_email)
            except EmailError:
                logger.error(
                    f"NOTIFY: Error sending email to supplier '{supplier_id}' user {hash_string(notify_email)}")
                if notify_fail_early:
                    raise
                else:
                    failed_send_email_calls += 1
    # just catching these exceptions for logging then reraising
    except (OSError, IOError) as e:
        logger.error("Error reading file '{}': {}".format(file_path, e.message))
        raise
    except S3ResponseError as e:
        logger.error("Error uploading '{}' to '{}': {}".format(file_path, upload_path, e.message))
        raise
    except APIError as e:
        logger.error("API error setting upload path '{}' on agreement ID {}: {}".format(
            upload_path,
            supplier_framework['agreementId'],
            e.message)
        )
        raise

    if failed_send_email_calls:
        raise EmailError("{} notify send_emails calls failed".format(failed_send_email_calls))
